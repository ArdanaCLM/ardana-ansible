#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2012, Michael DeHaan <michael.dehaan@gmail.com>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: service
author: Michael DeHaan
version_added: "0.1"
short_description:  Manage services.
description:
    - Controls services on remote hosts. Supported init systems include BSD init,
      OpenRC, SysV, Solaris SMF, systemd, upstart.
options:
    name:
        required: true
        description:
        - Name of the service.
    state:
        required: false
        choices: [ started, stopped, restarted, reloaded ]
        description:
          - C(started)/C(stopped) are idempotent actions that will not run
            commands unless necessary.  C(restarted) will always bounce the
            service.  C(reloaded) will always reload. B(At least one of state
            and enabled are required.)
    sleep:
        required: false
        version_added: "1.3"
        description:
        - If the service is being C(restarted) then sleep this many seconds
          between the stop and start command. This helps to workaround badly
          behaving init scripts that exit immediately after signaling a process
          to stop.
    pattern:
        required: false
        version_added: "0.7"
        description:
        - If the service does not respond to the status command, name a
          substring to look for as would be found in the output of the I(ps)
          command as a stand-in for a status result.  If the string is found,
          the service will be assumed to be running.
    enabled:
        required: false
        choices: [ "yes", "no" ]
        description:
        - Whether the service should start on boot. B(At least one of state and
          enabled are required.)

    runlevel:
        required: false
        default: 'default'
        description:
        - "For OpenRC init scripts (ex: Gentoo) only.  The runlevel that this service belongs to."
    arguments:
        description:
        - Additional arguments provided on the command line
        aliases: [ 'args' ]
'''

EXAMPLES = '''
# Example action to start service httpd, if not running
- service: name=httpd state=started

# Example action to stop service httpd, if running
- service: name=httpd state=stopped

# Example action to restart service httpd, in all cases
- service: name=httpd state=restarted

# Example action to reload service httpd, in all cases
- service: name=httpd state=reloaded

# Example action to enable service httpd, and not touch the running state
- service: name=httpd enabled=yes

# Example action to start service foo, based on running process /usr/bin/foo
- service: name=foo pattern=/usr/bin/foo state=started

# Example action to restart network service for interface eth0
- service: name=network state=restarted args=eth0
'''

import platform
import os
import re
import tempfile
import shlex
import select
import time
import string
import glob

# The distutils module is not shipped with SUNWPython on Solaris.
# It's in the SUNWPython-devel package which also contains development files
# that don't belong on production boxes.  Since our Solaris code doesn't
# depend on LooseVersion, do not import it on Solaris.
if platform.system() != 'SunOS':
    from distutils.version import LooseVersion

class Service(object):
    """
    This is the generic Service manipulation class that is subclassed
    based on platform.

    A subclass should override the following action methods:-
      - get_service_tools
      - service_enable
      - get_service_status
      - service_control

    All subclasses MUST define platform and distribution (which may be None).
    """

    platform = 'Generic'
    distribution = None

    def __new__(cls, *args, **kwargs):
        return load_platform_subclass(Service, args, kwargs)

    def __init__(self, module):
        self.module         = module
        self.name           = module.params['name']
        self.state          = module.params['state']
        self.sleep          = module.params['sleep']
        self.pattern        = module.params['pattern']
        self.enable         = module.params['enabled']
        self.runlevel       = module.params['runlevel']
        self.changed        = False
        self.running        = None
        self.crashed        = None
        self.action         = None
        self.svc_cmd        = None
        self.svc_initscript = None
        self.svc_initctl    = None
        self.enable_cmd     = None
        self.arguments      = module.params.get('arguments', '')
        self.rcconf_file    = None
        self.rcconf_key     = None
        self.rcconf_value   = None
        self.svc_change     = False

        # select whether we dump additional debug info through syslog
        self.syslogging = False

    # ===========================================
    # Platform specific methods (must be replaced by subclass).

    def get_service_tools(self):
        self.module.fail_json(msg="get_service_tools not implemented on target platform")

    def service_enable(self):
        self.module.fail_json(msg="service_enable not implemented on target platform")

    def get_service_status(self):
        self.module.fail_json(msg="get_service_status not implemented on target platform")

    def service_control(self):
        self.module.fail_json(msg="service_control not implemented on target platform")

    # ===========================================
    # Generic methods that should be used on all platforms.

    def execute_command(self, cmd, daemonize=False):
        if self.syslogging:
            syslog.openlog('ansible-%s' % os.path.basename(__file__))
            syslog.syslog(syslog.LOG_NOTICE, 'Command %s, daemonize %r' % (cmd, daemonize))

        # Most things don't need to be daemonized
        if not daemonize:
            return self.module.run_command(cmd)

        def check_pid_finished(pid):
            try:
                # signal 0 doesn't affect the process
                os.kill(pid, 0)
            except OSError as exc:
                if err.errno == errno.ESRCH:
                    # ESRCH == No such process
                    return True
                raise
            else:
                return False

        # This is complex because daemonization is hard for people.
        # What we do is daemonize a part of this module, the daemon runs the
        # command, picks up the return code and output, and returns it to the
        # main process.
        pipe = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(pipe[0])
            # Set stdin/stdout/stderr to /dev/null
            fd = os.open(os.devnull, os.O_RDWR)
            if fd != 0:
                os.dup2(fd, 0)
            if fd != 1:
                os.dup2(fd, 1)
            if fd != 2:
                os.dup2(fd, 2)
            if fd not in (0, 1, 2):
                os.close(fd)

            # Make us a daemon. Yes, that's all it takes.
            pid = os.fork()
            if pid > 0:
                os._exit(0)
            os.setsid()
            os.chdir("/")
            pid = os.fork()
            if pid > 0:
                os._exit(0)

            # Start the command
            if isinstance(cmd, basestring):
                cmd = shlex.split(cmd)
            p = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
            stdout = ""
            stderr = ""
            fds = [p.stdout, p.stderr]
            # Wait for all output, or until the main process is dead and its output is done.
            timeout = 1
            while fds:
                rfd, wfd, efd = select.select(fds, [], fds, timeout)
                if p.stdout in rfd:
                    dat = os.read(p.stdout.fileno(), 4096)
                    if not dat:
                        fds.remove(p.stdout)
                    stdout += dat
                if p.stderr in rfd:
                    dat = os.read(p.stderr.fileno(), 4096)
                    if not dat:
                        fds.remove(p.stderr)
                    stderr += dat

                # Has the child process exited?
                if p.poll() is not None:
                    if not fds or timeout == 0:
                        break

                    # Call select one more time with a zero timeout to be
                    # certain not to miss anything that may have been written
                    # to stdout/stderr between the time select() was called
                    # and learned that process has finished
                    timeout = 0

                # if the process has not yet exited, but already read EOF
                # from it's stdout/stderr (and thus removed both from fds)
                # can just wait for it to exit.
                elif not fds:
                    p.wait()
                    break

            # Return a JSON blob to parent
            os.write(pipe[1], json.dumps([p.returncode, stdout, stderr]))
            os.fsync(pipe[1])
            os.close(pipe[1])
            os._exit(0)
        elif pid == -1:
            self.module.fail_json(msg="unable to fork")
        else:
            os.close(pipe[1])
            # Wait for data from daemon process and process it.
            data = ""
            fds = [pipe[0]]
            timeout = 1
            while fds:
                rfd, wfd, efd = select.select(fds, [], fds, timeout)
                if pipe[0] in rfd:
                    dat = os.read(pipe[0], 4096)
                    if not dat:
                        fds.remove(pipe[0])
                    data += dat

                # Has the daemonized process exited?
                if check_pid_finished(pid):
                    if not fds or timeout == 0:
                        break

                    # Call select one more time with a zero timeout to be
                    # certain not to miss anything that may have been written
                    # to pipe[0] between the time select() was called and
                    # learned that the process has finished
                    timeout = 0

                # if the process has not yet exited, but already read EOF
                # from pipe[0] (and thus removed both from fds)
                # can just wait for it to exit.
                elif not fds:
                    os.waitpid(pid, 0)
                    break

            return json.loads(data)

    def check_ps(self):
        # Set ps flags
        if platform.system() == 'SunOS':
            psflags = '-ef'
        else:
            psflags = 'auxww'

        # Find ps binary
        psbin = self.module.get_bin_path('ps', True)

        (rc, psout, pserr) = self.execute_command('%s %s' % (psbin, psflags))
        # If rc is 0, set running as appropriate
        if rc == 0:
            self.running = False
            lines = psout.split("\n")
            for line in lines:
                if self.pattern in line and not "pattern=" in line:
                    # so as to not confuse ./hacking/test-module
                    self.running = True
                    break

    def check_service_changed(self):
        if self.state and self.running is None:
            self.module.fail_json(msg="failed determining service state, possible typo of service name?")
        # Find out if state has changed
        if not self.running and self.state in ["started", "running", "reloaded"]:
            self.svc_change = True
        elif self.running and self.state in ["stopped","reloaded"]:
            self.svc_change = True
        elif self.state == "restarted":
            self.svc_change = True
        if self.module.check_mode and self.svc_change:
            self.module.exit_json(changed=True, msg='service state changed')

    def modify_service_state(self):

        # Only do something if state will change
        if self.svc_change:
            # Control service
            if self.state in ['started', 'running']:
                self.action = "start"
            elif not self.running and self.state == 'reloaded':
                self.action = "start"
            elif self.state == 'stopped':
                self.action = "stop"
            elif self.state == 'reloaded':
                self.action = "reload"
            elif self.state == 'restarted':
                self.action = "restart"

            if self.module.check_mode:
                self.module.exit_json(changed=True, msg='changing service state')

            return self.service_control()

        else:
            # If nothing needs to change just say all is well
            rc = 0
            err = ''
            out = ''
            return rc, out, err

    def service_enable_rcconf(self):
        if self.rcconf_file is None or self.rcconf_key is None or self.rcconf_value is None:
            self.module.fail_json(msg="service_enable_rcconf() requires rcconf_file, rcconf_key and rcconf_value")

        self.changed = None
        entry = '%s="%s"\n' % (self.rcconf_key, self.rcconf_value)
        RCFILE = open(self.rcconf_file, "r")
        new_rc_conf = []

        # Build a list containing the possibly modified file.
        for rcline in RCFILE:
            # Parse line removing whitespaces, quotes, etc.
            rcarray = shlex.split(rcline, comments=True)
            if len(rcarray) >= 1 and '=' in rcarray[0]:
                (key, value) = rcarray[0].split("=", 1)
                if key == self.rcconf_key:
                    if value.upper() == self.rcconf_value:
                        # Since the proper entry already exists we can stop iterating.
                        self.changed = False
                        break
                    else:
                        # We found the key but the value is wrong, replace with new entry.
                        rcline = entry
                        self.changed = True

            # Add line to the list.
            new_rc_conf.append(rcline)

        # We are done with reading the current rc.conf, close it.
        RCFILE.close()

        # If we did not see any trace of our entry we need to add it.
        if self.changed is None:
            new_rc_conf.append(entry)
            self.changed = True

        if self.changed is True:

            if self.module.check_mode:
                self.module.exit_json(changed=True, msg="changing service enablement")

            # Create a temporary file next to the current rc.conf (so we stay on the same filesystem).
            # This way the replacement operation is atomic.
            rcconf_dir = os.path.dirname(self.rcconf_file)
            rcconf_base = os.path.basename(self.rcconf_file)
            (TMP_RCCONF, tmp_rcconf_file) = tempfile.mkstemp(dir=rcconf_dir, prefix="%s-" % rcconf_base)

            # Write out the contents of the list into our temporary file.
            for rcline in new_rc_conf:
                os.write(TMP_RCCONF, rcline)

            # Close temporary file.
            os.close(TMP_RCCONF)

            # Replace previous rc.conf.
            self.module.atomic_move(tmp_rcconf_file, self.rcconf_file)

# ===========================================
# Subclass: Linux

class LinuxService(Service):
    """
    This is the Linux Service manipulation class - it is currently supporting
    a mixture of binaries and init scripts for controlling services started at
    boot, as well as for controlling the current state.
    """

    platform = 'Linux'
    distribution = None

    def get_service_tools(self):

        paths = [ '/sbin', '/usr/sbin', '/bin', '/usr/bin' ]
        binaries = [ 'service', 'chkconfig', 'update-rc.d', 'rc-service', 'rc-update', 'initctl', 'systemctl', 'start', 'stop', 'restart', 'insserv' ]
        initpaths = [ '/etc/init.d' ]
        location = dict()

        for binary in binaries:
            location[binary] = self.module.get_bin_path(binary)

        for initdir in initpaths:
            initscript = "%s/%s" % (initdir,self.name)
            if os.path.isfile(initscript):
                self.svc_initscript = initscript

        def check_systemd():
            # verify systemd is installed (by finding systemctl)
            if not location.get('systemctl', False):
                return False

            systemd_enabled = False
            # Check if init is the systemd command, using comm as cmdline could be symlink
            try:
                f = open('/proc/1/comm', 'r')
            except IOError, err:
                # If comm doesn't exist, old kernel, no systemd
                return False

            for line in f:
                if 'systemd' in line:
                    return True

            return False

        # Locate a tool to enable/disable a service
        if location.get('systemctl',False) and check_systemd():
            # service is managed by systemd
            self.__systemd_unit = self.name
            self.svc_cmd = location['systemctl']
            self.enable_cmd = location['systemctl']

        elif location.get('initctl', False) and os.path.exists("/etc/init/%s.conf" % self.name):
            # service is managed by upstart
            self.enable_cmd = location['initctl']
            # set the upstart version based on the output of 'initctl version'
            self.upstart_version = LooseVersion('0.0.0')
            try:
                version_re = re.compile(r'\(upstart (.*)\)')
                rc,stdout,stderr = self.module.run_command('initctl version')
                if rc == 0:
                    res = version_re.search(stdout)
                    if res:
                        self.upstart_version = LooseVersion(res.groups()[0])
            except:
                pass  # we'll use the default of 0.0.0

            if location.get('start', False):
                # upstart -- rather than being managed by one command, start/stop/restart are actual commands
                self.svc_cmd = ''

        elif location.get('rc-service', False):
            # service is managed by OpenRC
            self.svc_cmd = location['rc-service']
            self.enable_cmd = location['rc-update']
            return # already have service start/stop tool too!

        elif self.svc_initscript:
            # service is managed by with SysV init scripts
            if location.get('update-rc.d', False):
                # and uses update-rc.d
                self.enable_cmd = location['update-rc.d']
            elif location.get('insserv', None):
                # and uses insserv
                self.enable_cmd = location['insserv']
            elif location.get('chkconfig', False):
                # and uses chkconfig
                self.enable_cmd = location['chkconfig']

        if self.enable_cmd is None:
            self.module.fail_json(msg="no service or tool found for: %s" % self.name)

        # If no service control tool selected yet, try to see if 'service' is available
        if self.svc_cmd is None and location.get('service', False):
            self.svc_cmd = location['service']

        # couldn't find anything yet
        if self.svc_cmd is None and not self.svc_initscript:
            self.module.fail_json(msg='cannot find \'service\' binary or init script for service,  possible typo in service name?, aborting')

        if location.get('initctl', False):
            self.svc_initctl = location['initctl']

    def get_systemd_service_enabled(self):
        (rc, out, err) = self.execute_command("%s is-enabled %s" % (self.enable_cmd, self.__systemd_unit,))
        if rc == 0:
            return True
        return False

    def get_systemd_status_dict(self):
        (rc, out, err) = self.execute_command("%s show %s" % (self.enable_cmd, self.__systemd_unit,))
        if rc != 0:
            self.module.fail_json(msg='failure %d running systemctl show for %r: %s' % (rc, self.__systemd_unit, err))
        key = None
        value_buffer = []
        status_dict = {}
        for line in out.splitlines():
            if not key:
                if not line:
                    continue
                key, value = line.split('=', 1)
                # systemd fields that are shell commands can be multi-line
                # We take a value that begins with a "{" as the start of
                # a shell command and a line that ends with "}" as the end of
                # the command
                if value.lstrip().startswith('{'):
                    if value.rstrip().endswith('}'):
                        status_dict[key] = value
                        key = None
                    else:
                        value_buffer.append(value)
                else:
                    status_dict[key] = value
                    key = None
            else:
                if line.rstrip().endswith('}'):
                    status_dict[key] = '\n'.join(value_buffer)
                    key = None
                else:
                    value_buffer.append(value)

        return status_dict

    def get_systemd_service_status(self):
        d = self.get_systemd_status_dict()
        if d.get('ActiveState') == 'active':
            # run-once services (for which a single successful exit indicates
            # that they are running as designed) should not be restarted here.
            # Thus, we are not checking d['SubState'].
            self.running = True
            self.crashed = False
        elif d.get('ActiveState') == 'failed':
            self.running = False
            self.crashed = True
        elif d.get('ActiveState') is None:
            self.module.fail_json(msg='No ActiveState value in systemctl show output for %r' % (self.__systemd_unit,))
        else:
            self.running = False
            self.crashed = False
        return self.running

    def get_service_status(self):
        if self.svc_cmd and self.svc_cmd.endswith('systemctl'):
            return self.get_systemd_service_status()

        self.action = "status"
        rc, status_stdout, status_stderr = self.service_control()

        # if we have decided the service is managed by upstart, we check for some additional output...
        if self.svc_initctl and self.running is None:
            # check the job status by upstart response
            initctl_rc, initctl_status_stdout, initctl_status_stderr = self.execute_command("%s status %s" % (self.svc_initctl, self.name))
            if "stop/waiting" in initctl_status_stdout:
                self.running = False
            elif "start/running" in initctl_status_stdout:
                self.running = True

        if self.svc_cmd and self.svc_cmd.endswith("rc-service") and self.running is None:
            openrc_rc, openrc_status_stdout, openrc_status_stderr = self.execute_command("%s %s status" % (self.svc_cmd, self.name))
            self.running = "started" in openrc_status_stdout
            self.crashed = "crashed" in openrc_status_stderr

        # if the job status is still not known check it by status output keywords
        # Only check keywords if there's only one line of output (some init
        # scripts will output verbosely in case of error and those can emit
        # keywords that are picked up as false positives
        if self.running is None and status_stdout.count('\n') <= 1:
            # first transform the status output that could irritate keyword matching
            cleanout = status_stdout.lower().replace(self.name.lower(), '')
            if "stop" in cleanout:
                self.running = False
            elif "run" in cleanout and "not" in cleanout:
                self.running = False
            elif "run" in cleanout and "not" not in cleanout:
                self.running = True
            elif "start" in cleanout and "not" not in cleanout:
                self.running = True
            elif 'could not access pid file' in cleanout:
                self.running = False
            elif 'is dead and pid file exists' in cleanout:
                self.running = False
            elif 'dead but subsys locked' in cleanout:
                self.running = False
            elif 'dead but pid file exists' in cleanout:
                self.running = False

        # if the job status is still not known check it by response code
        # For reference, see:
        # http://refspecs.linuxbase.org/LSB_4.1.0/LSB-Core-generic/LSB-Core-generic/iniscrptact.html
        if self.running is None:
            if rc in [1, 2, 3, 4, 69]:
                self.running = False
            elif rc == 0:
                self.running = True

        # if the job status is still not known check it by special conditions
        if self.running is None:
            if self.name == 'iptables' and "ACCEPT" in status_stdout:
                # iptables status command output is lame
                # TODO: lookup if we can use a return code for this instead?
                self.running = True

        return self.running


    def service_enable(self):

        if self.enable_cmd is None:
            self.module.fail_json(msg='cannot detect command to enable service %s, typo or init system potentially unknown' % self.name)

        self.changed = True
        action = None

        #
        # Upstart's initctl
        #
        if self.enable_cmd.endswith("initctl"):
            def write_to_override_file(file_name, file_contents, ):
                override_file = open(file_name, 'w')
                override_file.write(file_contents)
                override_file.close()

            initpath = '/etc/init'
            if self.upstart_version >= LooseVersion('0.6.7'):
                manreg = re.compile('^manual\s*$', re.M | re.I)
                config_line = 'manual\n'
            else:
                manreg = re.compile('^start on manual\s*$', re.M | re.I)
                config_line = 'start on manual\n'
            conf_file_name = "%s/%s.conf" % (initpath, self.name)
            override_file_name = "%s/%s.override" % (initpath, self.name)

            # Check to see if files contain the manual line in .conf and fail if True
            if manreg.search(open(conf_file_name).read()):
                self.module.fail_json(msg="manual stanza not supported in a .conf file")

            self.changed = False
            if os.path.exists(override_file_name):
                override_file_contents = open(override_file_name).read()
                # Remove manual stanza if present and service enabled
                if self.enable and manreg.search(override_file_contents):
                    self.changed = True
                    override_state = manreg.sub('', override_file_contents)
                # Add manual stanza if not present and service disabled
                elif not (self.enable) and not (manreg.search(override_file_contents)):
                    self.changed = True
                    override_state = '\n'.join((override_file_contents, config_line))
                # service already in desired state
                else:
                    pass
            # Add file with manual stanza if service disabled
            elif not (self.enable):
                self.changed = True
                override_state = config_line
            else:
                # service already in desired state
                pass

            if self.module.check_mode:
                self.module.exit_json(changed=self.changed)

            # The initctl method of enabling and disabling services is much
            # different than for the other service methods.  So actually
            # committing the change is done in this conditional and then we
            # skip the boilerplate at the bottom of the method
            if self.changed:
                try:
                    write_to_override_file(override_file_name, override_state)
                except:
                    self.module.fail_json(msg='Could not modify override file')

            return

        #
        # SysV's chkconfig
        #
        if self.enable_cmd.endswith("chkconfig"):
            if self.enable:
                action = 'on'
            else:
                action = 'off'

            (rc, out, err) = self.execute_command("%s --list %s" % (self.enable_cmd, self.name))
            if 'chkconfig --add %s' % self.name in err:
                self.execute_command("%s --add %s" % (self.enable_cmd, self.name))
                (rc, out, err) = self.execute_command("%s --list %s" % (self.enable_cmd, self.name))
            if not self.name in out:
                self.module.fail_json(msg="service %s does not support chkconfig" % self.name)
            state = out.split()[-1]

            # Check if we're already in the correct state
            if "3:%s" % action in out and "5:%s" % action in out:
                self.changed = False
                return

        #
        # Systemd's systemctl
        #
        if self.enable_cmd.endswith("systemctl"):
            if self.enable:
                action = 'enable'
            else:
                action = 'disable'

            # Check if we're already in the correct state
            service_enabled = self.get_systemd_service_enabled()

            # self.changed should already be true
            if self.enable == service_enabled:
                self.changed = False
                return

        #
        # OpenRC's rc-update
        #
        if self.enable_cmd.endswith("rc-update"):
            if self.enable:
                action = 'add'
            else:
                action = 'delete'

            (rc, out, err) = self.execute_command("%s show" % self.enable_cmd)
            for line in out.splitlines():
                service_name, runlevels = line.split('|')
                service_name = service_name.strip()
                if service_name != self.name:
                    continue
                runlevels = re.split(r'\s+', runlevels)
                # service already enabled for the runlevel
                if self.enable and self.runlevel in runlevels:
                    self.changed = False
                # service already disabled for the runlevel
                elif not self.enable and self.runlevel not in runlevels:
                    self.changed = False
                break
            else:
                # service already disabled altogether
                if not self.enable:
                    self.changed = False

            if not self.changed:
                return

        #
        # update-rc.d style
        #
        if self.enable_cmd.endswith("update-rc.d"):

            enabled = False
            slinks = glob.glob('/etc/rc?.d/S??' + self.name)
            if slinks:
                enabled = True

            if self.enable != enabled:
                self.changed = True

                if self.enable:
                    action = 'enable'
                    klinks = glob.glob('/etc/rc?.d/K??' + self.name)
                    if not klinks:
                        (rc, out, err) = self.execute_command("%s %s defaults"  % (self.enable_cmd, self.name))
                        if rc != 0:
                            if err:
                                self.module.fail_json(msg=err)
                            else:
                                self.module.fail_json(msg=out) % (self.enable_cmd, self.name, action)
                else:
                    action = 'disable'

                (rc, out, err) = self.execute_command("%s %s %s"  % (self.enable_cmd, self.name, action))
                if rc != 0:
                    if err:
                        self.module.fail_json(msg=err)
                    else:
                        self.module.fail_json(msg=out) % (self.enable_cmd, self.name, action)
            else:
                self.changed = False

            return

        #
        # insserv (Debian 7)
        #
        if self.enable_cmd.endswith("insserv"):
            if self.enable:
                (rc, out, err) = self.execute_command("%s -n %s" % (self.enable_cmd, self.name))
            else:
                (rc, out, err) = self.execute_command("%s -nr %s" % (self.enable_cmd, self.name))

            self.changed = False
            for line in err.splitlines():
                if self.enable and line.find('enable service') != -1:
                    self.changed = True
                    break
                if not self.enable and line.find('remove service') != -1:
                    self.changed = True
                    break

            if self.module.check_mode:
                self.module.exit_json(changed=self.changed)

            if not self.changed:
                return

            if self.enable:
                (rc, out, err) = self.execute_command("%s %s" % (self.enable_cmd, self.name))
                if (rc != 0) or (err != ''):
                    self.module.fail_json(msg=("Failed to install service. rc: %s, out: %s, err: %s" % (rc, out, err)))
                return (rc, out, err)
            else:
                (rc, out, err) = self.execute_command("%s -r %s" % (self.enable_cmd, self.name))
                if (rc != 0) or (err != ''):
                    self.module.fail_json(msg=("Failed to remove service. rc: %s, out: %s, err: %s" % (rc, out, err)))
                return (rc, out, err)

        #
        # If we've gotten to the end, the service needs to be updated
        #
        self.changed = True

        # we change argument order depending on real binary used:
        # rc-update and systemctl need the argument order reversed

        if self.enable_cmd.endswith("rc-update"):
            args = (self.enable_cmd, action, self.name + " " + self.runlevel)
        elif self.enable_cmd.endswith("systemctl"):
            args = (self.enable_cmd, action, self.__systemd_unit)
        else:
            args = (self.enable_cmd, self.name, action)

        if self.module.check_mode:
            self.module.exit_json(changed=self.changed)

        (rc, out, err) = self.execute_command("%s %s %s" % args)
        if rc != 0:
            if err:
                self.module.fail_json(msg="Error when trying to %s %s: rc=%s %s" % (action, self.name, rc, err))
            else:
                self.module.fail_json(msg="Failure for %s %s: rc=%s %s" % (action, self.name, rc, out))

        return (rc, out, err)


    def service_control(self):

        # Decide what command to run
        svc_cmd = ''
        arguments = self.arguments
        if self.svc_cmd:
            if not self.svc_cmd.endswith("systemctl"):
                # SysV and OpenRC take the form <cmd> <name> <action>
                svc_cmd = "%s %s" % (self.svc_cmd, self.name)
            else:
                # systemd commands take the form <cmd> <action> <name>
                svc_cmd = self.svc_cmd
                arguments = "%s %s" % (self.__systemd_unit, arguments)
        elif self.svc_cmd is None and self.svc_initscript:
            # upstart
            svc_cmd = "%s" % self.svc_initscript

        # In OpenRC, if a service crashed, we need to reset its status to
        # stopped with the zap command, before we can start it back.
        if self.svc_cmd and self.svc_cmd.endswith('rc-service') and self.action == 'start' and self.crashed:
            self.execute_command("%s zap" % svc_cmd, daemonize=True)

        if self.action is not "restart":
            if svc_cmd != '':
                # upstart or systemd or OpenRC
                rc_state, stdout, stderr = self.execute_command("%s %s %s" % (svc_cmd, self.action, arguments), daemonize=True)
            else:
                # SysV
                rc_state, stdout, stderr = self.execute_command("%s %s %s" % (self.action, self.name, arguments), daemonize=True)
        elif self.svc_cmd and self.svc_cmd.endswith('rc-service'):
            # All services in OpenRC support restart.
            rc_state, stdout, stderr = self.execute_command("%s %s %s" % (svc_cmd, self.action, arguments), daemonize=True)
        else:
            # In other systems, not all services support restart. Do it the hard way.
            if svc_cmd != '':
                # upstart or systemd
                rc1, stdout1, stderr1 = self.execute_command("%s %s %s" % (svc_cmd, 'stop', arguments), daemonize=True)
            else:
                # SysV
                rc1, stdout1, stderr1 = self.execute_command("%s %s %s" % ('stop', self.name, arguments), daemonize=True)

            if self.sleep:
                time.sleep(self.sleep)

            if svc_cmd != '':
                # upstart or systemd
                rc2, stdout2, stderr2 = self.execute_command("%s %s %s" % (svc_cmd, 'start', arguments), daemonize=True)
            else:
                # SysV
                rc2, stdout2, stderr2 = self.execute_command("%s %s %s" % ('start', self.name, arguments), daemonize=True)

            # merge return information
            if rc1 != 0 and rc2 == 0:
                rc_state = rc2
                stdout = stdout2
                stderr = stderr2
            else:
                rc_state = rc1 + rc2
                stdout = stdout1 + stdout2
                stderr = stderr1 + stderr2

        return(rc_state, stdout, stderr)

# ===========================================
# Subclass: FreeBSD

class FreeBsdService(Service):
    """
    This is the FreeBSD Service manipulation class - it uses the /etc/rc.conf
    file for controlling services started at boot and the 'service' binary to
    check status and perform direct service manipulation.
    """

    platform = 'FreeBSD'
    distribution = None

    def get_service_tools(self):
        self.svc_cmd = self.module.get_bin_path('service', True)

        if not self.svc_cmd:
            self.module.fail_json(msg='unable to find service binary')

    def get_service_status(self):
        rc, stdout, stderr = self.execute_command("%s %s %s %s" % (self.svc_cmd, self.name, 'onestatus', self.arguments))
        if rc == 1:
            self.running = False
        elif rc == 0:
            self.running = True

    def service_enable(self):
        if self.enable:
            self.rcconf_value = "YES"
        else:
            self.rcconf_value = "NO"

        rcfiles = [ '/etc/rc.conf','/etc/rc.conf.local', '/usr/local/etc/rc.conf' ]
        for rcfile in rcfiles:
            if os.path.isfile(rcfile):
                self.rcconf_file = rcfile

        rc, stdout, stderr = self.execute_command("%s %s %s %s" % (self.svc_cmd, self.name, 'rcvar', self.arguments))
        cmd = "%s %s %s %s" % (self.svc_cmd, self.name, 'rcvar', self.arguments)
        rcvars = shlex.split(stdout, comments=True)

        if not rcvars:
            self.module.fail_json(msg="unable to determine rcvar", stdout=stdout, stderr=stderr)

        # In rare cases, i.e. sendmail, rcvar can return several key=value pairs
        # Usually there is just one, however.  In other rare cases, i.e. uwsgi,
        # rcvar can return extra uncommented data that is not at all related to
        # the rcvar.  We will just take the first key=value pair we come across
        # and hope for the best.
        for rcvar in rcvars:
            if '=' in rcvar:
                self.rcconf_key = rcvar.split('=')[0]
                break

        if self.rcconf_key is None:
            self.module.fail_json(msg="unable to determine rcvar", stdout=stdout, stderr=stderr)

        try:
            return self.service_enable_rcconf()
        except:
            self.module.fail_json(msg='unable to set rcvar')

    def service_control(self):

        if self.action is "start":
            self.action = "onestart"
        if self.action is "stop":
            self.action = "onestop"
        if self.action is "reload":
            self.action = "onereload"

        return self.execute_command("%s %s %s %s" % (self.svc_cmd, self.name, self.action, self.arguments))

# ===========================================
# Subclass: OpenBSD

class OpenBsdService(Service):
    """
    This is the OpenBSD Service manipulation class - it uses rcctl(8) or
    /etc/rc.d scripts for service control. Enabling a service is
    only supported if rcctl is present.
    """

    platform = 'OpenBSD'
    distribution = None

    def get_service_tools(self):
        self.enable_cmd = self.module.get_bin_path('rcctl')

        if self.enable_cmd:
            self.svc_cmd = self.enable_cmd
        else:
            rcdir = '/etc/rc.d'

            rc_script = "%s/%s" % (rcdir, self.name)
            if os.path.isfile(rc_script):
                self.svc_cmd = rc_script

        if not self.svc_cmd:
            self.module.fail_json(msg='unable to find svc_cmd')

    def get_service_status(self):
        if self.enable_cmd:
            rc, stdout, stderr = self.execute_command("%s %s %s" % (self.svc_cmd, 'check', self.name))
        else:
            rc, stdout, stderr = self.execute_command("%s %s" % (self.svc_cmd, 'check'))

        if stderr:
            self.module.fail_json(msg=stderr)

        if rc == 1:
            self.running = False
        elif rc == 0:
            self.running = True

    def service_control(self):
        if self.enable_cmd:
            return self.execute_command("%s -f %s %s" % (self.svc_cmd, self.action, self.name))
        else:
            return self.execute_command("%s -f %s" % (self.svc_cmd, self.action))

    def service_enable(self):
        if not self.enable_cmd:
            return super(OpenBsdService, self).service_enable()

        rc, stdout, stderr = self.execute_command("%s %s %s %s" % (self.enable_cmd, 'getdef', self.name, 'flags'))

        if stderr:
            self.module.fail_json(msg=stderr)

        getdef_string = stdout.rstrip()

        # Depending on the service the string returned from 'default' may be
        # either a set of flags or the boolean YES/NO
        if getdef_string == "YES" or getdef_string == "NO":
            default_flags = ''
        else:
            default_flags = getdef_string

        rc, stdout, stderr = self.execute_command("%s %s %s %s" % (self.enable_cmd, 'get', self.name, 'flags'))

        if stderr:
            self.module.fail_json(msg=stderr)

        get_string = stdout.rstrip()

        # Depending on the service the string returned from 'getdef/get' may be
        # either a set of flags or the boolean YES/NO
        if get_string == "YES" or get_string == "NO":
            current_flags = ''
        else:
            current_flags = get_string

        # If there are arguments from the user we use these as flags unless
        # they are already set.
        if self.arguments and self.arguments != current_flags:
            changed_flags = self.arguments
        # If the user has not supplied any arguments and the current flags
        # differ from the default we reset them.
        elif not self.arguments and current_flags != default_flags:
            changed_flags = ' '
        # Otherwise there is no need to modify flags.
        else:
            changed_flags = ''

        rc, stdout, stderr = self.execute_command("%s %s %s %s" % (self.enable_cmd, 'get', self.name, 'status'))

        if self.enable:
            if rc == 0 and not changed_flags:
                return

            if rc != 0:
                status_action = "set %s status on" % (self.name)
            else:
                status_action = ''
            if changed_flags:
                flags_action = "set %s flags %s" % (self.name, changed_flags)
            else:
                flags_action = ''
        else:
            if rc == 1:
                return

            status_action = "set %s status off" % self.name
            flags_action = ''

        # Verify state assumption
        if not status_action and not flags_action:
            self.module.fail_json(msg="neither status_action or status_flags is set, this should never happen")

        if self.module.check_mode:
            self.module.exit_json(changed=True, msg="changing service enablement")

        status_modified = 0
        if status_action:
            rc, stdout, stderr = self.execute_command("%s %s" % (self.enable_cmd, status_action))

            if rc != 0:
                if stderr:
                    self.module.fail_json(msg=stderr)
                else:
                    self.module.fail_json(msg="rcctl failed to modify service status")

            status_modified = 1

        if flags_action:
            rc, stdout, stderr = self.execute_command("%s %s" % (self.enable_cmd, flags_action))

            if rc != 0:
                if stderr:
                    if status_modified:
                        error_message = "rcctl modified service status but failed to set flags: " + stderr
                    else:
                        error_message = stderr
                else:
                    if status_modified:
                        error_message = "rcctl modified service status but failed to set flags"
                    else:
                        error_message = "rcctl failed to modify service flags"

                self.module.fail_json(msg=error_message)

        self.changed = True

# ===========================================
# Subclass: NetBSD

class NetBsdService(Service):
    """
    This is the NetBSD Service manipulation class - it uses the /etc/rc.conf
    file for controlling services started at boot, check status and perform
    direct service manipulation. Init scripts in /etc/rcd are used for
    controlling services (start/stop) as well as for controlling the current
    state.
    """

    platform = 'NetBSD'
    distribution = None

    def get_service_tools(self):
        initpaths = [ '/etc/rc.d' ]		# better: $rc_directories - how to get in here? Run: sh -c '. /etc/rc.conf ; echo $rc_directories'

        for initdir in initpaths:
            initscript = "%s/%s" % (initdir,self.name)
            if os.path.isfile(initscript):
                self.svc_initscript = initscript

        if not self.svc_initscript:
            self.module.fail_json(msg='unable to find rc.d script')

    def service_enable(self):
        if self.enable:
            self.rcconf_value = "YES"
        else:
            self.rcconf_value = "NO"

        rcfiles = [ '/etc/rc.conf' ]		# Overkill?
        for rcfile in rcfiles:
            if os.path.isfile(rcfile):
                self.rcconf_file = rcfile

        self.rcconf_key = "%s" % string.replace(self.name,"-","_")

        return self.service_enable_rcconf()

    def get_service_status(self):
        self.svc_cmd = "%s" % self.svc_initscript
        rc, stdout, stderr = self.execute_command("%s %s" % (self.svc_cmd, 'onestatus'))
        if rc == 1:
            self.running = False
        elif rc == 0:
            self.running = True

    def service_control(self):
        if self.action is "start":
            self.action = "onestart"
        if self.action is "stop":
            self.action = "onestop"

        self.svc_cmd = "%s" % self.svc_initscript
        return self.execute_command("%s %s" % (self.svc_cmd, self.action), daemonize=True)

# ===========================================
# Subclass: SunOS
class SunOSService(Service):
    """
    This is the SunOS Service manipulation class - it uses the svcadm
    command for controlling services, and svcs command for checking status.
    It also tries to be smart about taking the service out of maintenance
    state if necessary.
    """
    platform = 'SunOS'
    distribution = None

    def get_service_tools(self):
        self.svcs_cmd = self.module.get_bin_path('svcs', True)

        if not self.svcs_cmd:
            self.module.fail_json(msg='unable to find svcs binary')

        self.svcadm_cmd = self.module.get_bin_path('svcadm', True)

        if not self.svcadm_cmd:
            self.module.fail_json(msg='unable to find svcadm binary')

    def get_service_status(self):
        status = self.get_sunos_svcs_status()
        # Only 'online' is considered properly running. Everything else is off
        # or has some sort of problem.
        if status == 'online':
            self.running = True
        else:
            self.running = False

    def get_sunos_svcs_status(self):
        rc, stdout, stderr = self.execute_command("%s %s" % (self.svcs_cmd, self.name))
        if rc == 1:
            if stderr:
                self.module.fail_json(msg=stderr)
            else:
                self.module.fail_json(msg=stdout)

        lines = stdout.rstrip("\n").split("\n")
        status = lines[-1].split(" ")[0]
        # status is one of: online, offline, degraded, disabled, maintenance, uninitialized
        # see man svcs(1)
        return status

    def service_enable(self):
        # Get current service enablement status
        rc, stdout, stderr = self.execute_command("%s -l %s" % (self.svcs_cmd, self.name))

        if rc != 0:
            if stderr:
                self.module.fail_json(msg=stderr)
            else:
                self.module.fail_json(msg=stdout)

        enabled = False
        temporary = False

        # look for enabled line, which could be one of:
        #    enabled   true (temporary)
        #    enabled   false (temporary)
        #    enabled   true
        #    enabled   false
        for line in stdout.split("\n"):
            if line.startswith("enabled"):
                if "true" in line:
                    enabled = True
                if "temporary" in line:
                    temporary = True

        startup_enabled = (enabled and not temporary) or (not enabled and temporary)

        if self.enable and startup_enabled:
            return
        elif (not self.enable) and (not startup_enabled):
            return

        # Mark service as started or stopped (this will have the side effect of
        # actually stopping or starting the service)
        if self.enable:
            subcmd = "enable -rs"
        else:
            subcmd = "disable -s"

        rc, stdout, stderr = self.execute_command("%s %s %s" % (self.svcadm_cmd, subcmd, self.name))

        if rc != 0:
            if stderr:
                self.module.fail_json(msg=stderr)
            else:
                self.module.fail_json(msg=stdout)

        self.changed = True


    def service_control(self):
        status = self.get_sunos_svcs_status()

        # if starting or reloading, clear maintenace states
        if self.action in ['start', 'reload', 'restart'] and status in ['maintenance', 'degraded']:
            rc, stdout, stderr = self.execute_command("%s clear %s" % (self.svcadm_cmd, self.name))
            if rc != 0:
                return rc, stdout, stderr
            status = self.get_sunos_svcs_status()

        if status in ['maintenance', 'degraded']:
            self.module.fail_json(msg="Failed to bring service out of %s status." % status)

        if self.action == 'start':
            subcmd = "enable -rst"
        elif self.action == 'stop':
            subcmd = "disable -st"
        elif self.action == 'reload':
            subcmd = "refresh"
        elif self.action == 'restart' and status == 'online':
            subcmd = "restart"
        elif self.action == 'restart' and status != 'online':
            subcmd = "enable -rst"

        return self.execute_command("%s %s %s" % (self.svcadm_cmd, subcmd, self.name))

# ===========================================
# Subclass: AIX

class AIX(Service):
    """
    This is the AIX Service (SRC) manipulation class - it uses lssrc, startsrc, stopsrc
    and refresh for service control. Enabling a service is currently not supported.
    Would require to add an entry in the /etc/inittab file (mkitab, chitab and rmitab
    commands)
    """

    platform = 'AIX'
    distribution = None

    def get_service_tools(self):
        self.lssrc_cmd = self.module.get_bin_path('lssrc', True)

        if not self.lssrc_cmd:
            self.module.fail_json(msg='unable to find lssrc binary')

        self.startsrc_cmd = self.module.get_bin_path('startsrc', True)

        if not self.startsrc_cmd:
            self.module.fail_json(msg='unable to find startsrc binary')

        self.stopsrc_cmd = self.module.get_bin_path('stopsrc', True)

        if not self.stopsrc_cmd:
            self.module.fail_json(msg='unable to find stopsrc binary')

        self.refresh_cmd = self.module.get_bin_path('refresh', True)

        if not self.refresh_cmd:
            self.module.fail_json(msg='unable to find refresh binary')


    def get_service_status(self):
        status = self.get_aix_src_status()
        # Only 'active' is considered properly running. Everything else is off
        # or has some sort of problem.
        if status == 'active':
            self.running = True
        else:
            self.running = False

    def get_aix_src_status(self):
        rc, stdout, stderr = self.execute_command("%s -s %s" % (self.lssrc_cmd, self.name))
        if rc == 1:
            if stderr:
                self.module.fail_json(msg=stderr)
            else:
                self.module.fail_json(msg=stdout)

        lines = stdout.rstrip("\n").split("\n")
        status = lines[-1].split(" ")[-1]
        # status is one of: active, inoperative
        return status

    def service_control(self):
        if self.action == 'start':
            srccmd = self.startsrc_cmd
        elif self.action == 'stop':
            srccmd = self.stopsrc_cmd
        elif self.action == 'reload':
            srccmd = self.refresh_cmd
        elif self.action == 'restart':
            self.execute_command("%s -s %s" % (self.stopsrc_cmd, self.name))
            srccmd = self.startsrc_cmd

        if self.arguments and self.action == 'start':
            return self.execute_command("%s -a \"%s\" -s %s" % (srccmd, self.arguments, self.name))
        else:
            return self.execute_command("%s -s %s" % (srccmd, self.name))


# ===========================================
# Main control flow

def main():
    module = AnsibleModule(
        argument_spec = dict(
            name = dict(required=True),
            state = dict(choices=['running', 'started', 'stopped', 'restarted', 'reloaded']),
            sleep = dict(required=False, type='int', default=None),
            pattern = dict(required=False, default=None),
            enabled = dict(type='bool'),
            runlevel = dict(required=False, default='default'),
            arguments = dict(aliases=['args'], default=''),
        ),
        supports_check_mode=True
    )
    if module.params['state'] is None and module.params['enabled'] is None:
        module.fail_json(msg="Neither 'state' nor 'enabled' set")

    service = Service(module)

    if service.syslogging:
        syslog.openlog('ansible-%s' % os.path.basename(__file__))
        syslog.syslog(syslog.LOG_NOTICE, 'Service instantiated - platform %s' % service.platform)
        if service.distribution:
            syslog.syslog(syslog.LOG_NOTICE, 'Service instantiated - distribution %s' % service.distribution)

    rc = 0
    out = ''
    err = ''
    result = {}
    result['name'] = service.name

    # Find service management tools
    service.get_service_tools()

    # Enable/disable service startup at boot if requested
    if service.module.params['enabled'] is not None:
        # FIXME: ideally this should detect if we need to toggle the enablement state, though
        # it's unlikely the changed handler would need to fire in this case so it's a minor thing.
        service.service_enable()
        result['enabled'] = service.enable

    if module.params['state'] is None:
        # Not changing the running state, so bail out now.
        result['changed'] = service.changed
        module.exit_json(**result)

    result['state'] = service.state

    # Collect service status
    if service.pattern:
        service.check_ps()
    else:
        service.get_service_status()

    # Calculate if request will change service state
    service.check_service_changed()

    # Modify service state if necessary
    (rc, out, err) = service.modify_service_state()

    if rc != 0:
        if err and "Job is already running" in err:
            # upstart got confused, one such possibility is MySQL on Ubuntu 12.04
            # where status may report it has no start/stop links and we could
            # not get accurate status
            pass
        else:
            if err:
                module.fail_json(msg=err)
            else:
                module.fail_json(msg=out)

    result['changed'] = service.changed | service.svc_change
    if service.module.params['enabled'] is not None:
        result['enabled'] = service.module.params['enabled']

    if not service.module.params['state']:
        status = service.get_service_status()
        if status is None:
            result['state'] = 'absent'
        elif status is False:
            result['state'] = 'started'
        else:
            result['state'] = 'stopped'
    else:
        # as we may have just bounced the service the service command may not
        # report accurate state at this moment so just show what we ran
        if service.module.params['state'] in ['started','restarted','running','reloaded']:
            result['state'] = 'started'
        else:
            result['state'] = 'stopped'

    module.exit_json(**result)

from ansible.module_utils.basic import *
main()
