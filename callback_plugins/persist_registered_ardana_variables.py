#
# Apply callback plugin to Ansible to persist certain variables
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

from jinja2 import parser
from jinja2 import environment
from jinja2 import nodes
from ansible import utils
from ansible import constants as C
from ansible.errors import AnsibleError

import fcntl
import os

from copy import deepcopy

try:
    from ansible.callbacks import display
except ImportError:
    # v2.0 import
    from ansible.utils.display import Display
    my_display = Display()
    display = my_display.warning

ARDANA_PREFIX = "ardana_notify"

def search_node(node, parent_not=False):
    if isinstance(node, nodes.And):
        for child in (node.left, node.right):
            for value in search_node(child):
                yield value
    elif isinstance(node, nodes.Or):
        for child in (node.left, node.right):
            for value in search_node(child):
                yield value
    elif isinstance(node, nodes.Not):
        for value in search_node(node.node, parent_not=True):
            yield value
    elif isinstance(node, nodes.Test):
        if (hasattr(node, 'name') and node.name == "defined"
           and hasattr(node.node, 'name') and node.node.name.startswith(ARDANA_PREFIX)
           and node.node.ctx == "load" and not parent_not):
            yield node.node.name

#
# This function processes the fact cache host entries to remove registered
# ARDANA_PREFIX variables marked for deletion, along with the deletion markers.
#

def _clear_prefix_from_cache(cache, PREFIX):
    corrupt_files = []
    for key in cache:
        try:
            for host_key in cache[key].keys():
                if (host_key.startswith(PREFIX) and host_key.endswith(".deleted")
                   and cache[key].get(host_key, "False")):
                    _key = host_key.split(".deleted")[0]
                    del cache[key][host_key]
                    if _key in cache[key]:
                        del cache[key][_key]
        except Exception:
            display("Fact cache entry for host %s isn't valid, deleting and failing" % key)
            # This next bit only works for JSON fact-cache
            if C.CACHE_PLUGIN == "jsonfile":
                try:
                    os.remove("%s/%s" % (C.CACHE_PLUGIN_CONNECTION, key))
                except (OSError, IOError):
                    display("Couldn't remove cache entry")
                finally:
                    corrupt_files.append(key)
    if len(corrupt_files) > 0:
        files = ', '.join(corrupt_files)
        raise AnsibleError("The JSON cache files %s were corrupt, or did not otherwise contain valid JSON data."
                           " They have been removed, so you can re-run your command now." % files)


def clear_from_cache(cache):
        _clear_prefix_from_cache(cache, ARDANA_PREFIX)



#
# This function is to fix an issue when using "become: true" whereby the HOME is set to
# "/root" and USER is set to "root" in the ansible_env entry in hosts' fact_cache.
# This issue might be fixed in Ansible v2.0, see https://github.com/ansible/ansible/issues/13592
#
def set_ansible_env_HOME(cache):
    for key in cache:
        if 'ansible_env' in cache[key] and cache[key]['ansible_env'].get('HOME') == '/root':
            cache[key]['ansible_env']['HOME'] = os.environ.get('HOME')
            cache[key]['ansible_env']['USER'] = os.environ.get('USER')


class CallbackModule(object):

    def playbook_on_start(self):
        if (C.CACHE_PLUGIN_CONNECTION is None or
           os.getenv("ANSIBLE_PERSIST_VARIABLES_DISABLE") is not None):
            return

        # Remove saved variables from persistent fact_cache if marked for deletion
        # if last run was ctrl-Ced before completion
        clear_from_cache(self.playbook.SETUP_CACHE)
        # Fix-up ansible_env HOME and USER entries if they are set to root
        set_ansible_env_HOME(self.playbook.SETUP_CACHE)

    def playbook_on_task_start(self, name, is_conditional):
        if (C.CACHE_PLUGIN_CONNECTION is None or
           os.getenv("ANSIBLE_PERSIST_VARIABLES_DISABLE") is not None):
            return

        for host in self.playbook.inventory.list_hosts():
            if host in self.playbook.SETUP_CACHE:
                for key, value in self.playbook.SETUP_CACHE[host].iteritems():
                    if key.startswith(ARDANA_PREFIX):
                        self._update_hash(self.playbook.VARS_CACHE, host, {key: value})

    def _get_target_host(self, host):
        if self.task.delegate_to is None:
            return host
        else:
            # The only way to work out the delegated host is to split the string apart.
            return host.split(' -> ')[-1]

    def _process_persistent_variables(self, host, res, PREFIX):
        _notify_set_false_prefix = PREFIX + "_set_false_prefix"

        if self.task.register and self.task.register == _notify_set_false_prefix:
            # Get _notify variables from SETUP_CACHE and set changed to False
            update_dict = {}
            prefix_to_set_false = PREFIX
            if _notify_set_false_prefix in self.playbook.VARS_CACHE[host]:
                prefix = self.playbook.VARS_CACHE[host].pop(_notify_set_false_prefix)
                prefix_to_set_false = prefix if prefix.startswith(PREFIX) else PREFIX
            for key in self.playbook.SETUP_CACHE[host]:
                if key.startswith(prefix_to_set_false) and not key.endswith(".deleted"):
                    new_state = deepcopy(self.playbook.SETUP_CACHE[host][key])
                    if new_state.get("changed", True):
                        new_state["changed"] = False
                        update_dict[key] = new_state
            if update_dict:
                res.update(update_dict)
                self._update_hash(res, "ansible_facts", update_dict)

        elif self.task.register and self.task.register.startswith(PREFIX):
            my_host = self._get_target_host(host)

            if res.get('changed'):
                # save the facts immediately in case there is an exception elsewhere
                self._update_hash(self.playbook.SETUP_CACHE, my_host,
                                  {self.task.register: res})

                if my_host == host:
                    # return a copy of the result data for ansible to save as well when
                    # it writes down facts after the task is complete on all hosts
                    result = {k: v for k, v in res.items() if k != 'ansible_facts'}
                    self._update_hash(res, 'ansible_facts',
                                      {self.task.register: result})

            else:
                previous_state = self.playbook.SETUP_CACHE[my_host].get(self.task.register)
                if previous_state:
                    res.update(previous_state)
                    result = {k: v for k, v in res.items() if k != 'ansible_facts'}
                    self._update_hash(res, 'ansible_facts',
                                      {self.task.register: result})

        if self.task.when:
            if isinstance(self.task.when, list):
                when = None
                for elem in self.task.when:
                    if PREFIX in elem:
                        when = elem
            else:
                when = self.task.when if PREFIX in self.task.when else None
            if when:
                # Mark saved variable for removal from persistent cache at end of run
                # if check is "is defined"
                my_host = self._get_target_host(host)
                envir = environment.Environment()
                when = when.replace('{{', '')
                when = when.replace('}}', '')
                parse = parser.Parser(envir, when, state='variable')
                expr = parse.parse_expression()
                deleted_keys = {}
                for key in search_node(expr):
                    deleted_keys["%s.deleted" % key] = True

                self._update_hash(res, 'ansible_facts', deleted_keys)

                # If delegating task, mark persisted facts for deletion on node to which
                # you're delegating
                if my_host != host:
                    self._update_hash(self.playbook.SETUP_CACHE, my_host, deleted_keys)

    def runner_on_ok(self, host, res):
        if (C.CACHE_PLUGIN_CONNECTION is None or
           os.getenv("ANSIBLE_PERSIST_VARIABLES_DISABLE") is not None):
            return

        if self.task:
            self._process_persistent_variables(host, res, ARDANA_PREFIX)

    def _update_hash(self, hash, key, new_value):
        # If two or more nodes delegate to the same node and attempt to update
        # the fact-cache for that node simultaneously we need to lock using
        # mutex around the update_hash action to stop a collision.
        # Because instances of this callback plugin live within multiple subprocesses
        # during execution, we can't rely on a threading.RLock; nor can we use a
        # POSIX multiprocess.Lock object since there's no way to ensure that the
        # object is correctly created in the parent process.
        # Instead, we'll use a traditional file-based lock for the key item.
        with open("%s/.lock_%s" % (C.CACHE_PLUGIN_CONNECTION, key), "w+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            utils.update_hash(hash, key, new_value)

    def playbook_on_stats(self, stats):
        if (C.CACHE_PLUGIN_CONNECTION is None or
           os.getenv("ANSIBLE_PERSIST_VARIABLES_DISABLE") is not None):
            return

        # Remove saved variables from persistent fact_cache if marked for deletion
        clear_from_cache(self.playbook.SETUP_CACHE)
