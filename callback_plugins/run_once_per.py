#
# Apply run_once_per: to Ansible that runs a tasks given a group of hosts
# (c) Copyright 2016 Hewlett Packard Enterprise Development LP
# (c) Copyright 2017 SUSE LLC
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# his program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# For Ansible 1.9.x

# Apply run_once_per: to ansible tasks.
# Usage:
# On a task with run_once_per set, the value of the run_once_per
# expression will be computed per host in play. Those hosts are
# grouped by the result; the task is then executed once per unique
# value in the result, on the first host in play that evaluated to
# that result.

# Example: in hosts/foo:
# a ansible_ssh_connection=127.0.0.1 bar=1
# b ansible_ssh_connection=127.0.0.1 bar=1
# c ansible_ssh_connection=127.0.0.1 bar=2
# d ansible_ssh_connection=127.0.0.1 bar=2
#
# - debug:
#     msg: "the value of bar is {{ bar }}"
#   run_once_per: bar
#
# This will evaluate the J2 expression, resulting in
# a->1 b->1 c->2 d->2.
# Then hosts a and c will be selected for the task.


import collections

from ansible.callbacks import vv, vvv
from ansible.utils import template


class CallbackModule(object):

    def playbook_on_start(this):
        """ Ansible doesn't provide the hooks for this.
            Instead we inject our code into the appropriate
            modules during initialisation.
        """

        # Monkey-patch ansible.playbook.task.Task
        import ansible.playbook.task

        class T(ansible.playbook.task.Task):
            VALID_KEYS = ansible.playbook.task.Task.VALID_KEYS.union({'run_once_per'})

            def __init__(self, play, ds, **kwargs):
                super(T, self).__init__(play, ds, **kwargs)
                self.run_once_per = ds.get('run_once_per')

        ansible.playbook.task.Task = T

        # We'll need to get ansible.playbook.play.Task too
        import ansible.playbook.play
        ansible.playbook.play.Task = T

        # Monkey-patch ansible.runner.Runner.run
        import ansible.runner

        old_run = ansible.runner.Runner.run
        def run(self):
            # Work out the hosts to run on.
            if this.task is None or this.task.run_once_per is None:
                return old_run(self)

            per_expr = "{{" + this.task.run_once_per + "}}"

            # Evaluate that expression per current host.
            groups = collections.defaultdict(list)

            if not self.run_hosts:
                self.run_hosts = self.inventory.list_hosts(self.pattern)
            hosts = self.run_hosts

            if len(hosts) == 0:
                return old_run(self)

            for host in hosts:
                inject = self.get_inject_vars(host)
                value = template.template(self.basedir, per_expr, inject, fail_on_undefined=True)
                vvv("evaluating {} for {} and got {!r}".format(per_expr, host, value))
                groups[value].append(host)

            vv("run_once_per for each of {!r}".format(groups))
            try:
                self.run_hosts = [groups[value][0] for value in groups]
                return old_run(self)
            finally:
                self.run_hosts = hosts

        ansible.runner.Runner.run = run
