#!/usr/bin/env python
#
# An Ansible module to query apt for the list of packages
# available for update.
#
# (c) Copyright 2015-2016 Hewlett Packard Enterprise Development LP
# (c) Copyright 2017 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

DOCUMENTATION = '''
---
module: dpkg_list
author: Tom Howley
short_description: Queries apt for list of packages available for upgrade.
description:
    - Updates the local apt cache.
    - Queries the apt cache to get the list of packages avalailable for upgrade.
      That list of packages is written to the fact: list_pkg_upgrades
options:
    Currently no options.
'''

EXAMPLES = '''
- dpkg_list:
'''

import subprocess


def get_installed_pkgs(module):
    dpkg_query_bin = module.get_bin_path('dpkg-query')
    cmd = [dpkg_query_bin, '-W', "-f=${Package} ${Version}\n"]
    output = subprocess.check_output(cmd).splitlines()
    installed_pkgs = {}

    for line in output:
        (pkg, version) = line.split()
        installed_pkgs[pkg] = {"Version": version}

    return installed_pkgs


def main():

    module = AnsibleModule(argument_spec=dict())
    installed_pkgs = get_installed_pkgs(module)
    changed = False
    ansible_facts_dict = dict(installed_pkgs=installed_pkgs)
    result = dict(changed=changed, ansible_facts=ansible_facts_dict)
    module.exit_json(**result)

from ansible.module_utils.basic import *
main()
