#!/usr/bin/env python
#
# An Ansible module to query timestamped openstack packages installed on the
# system
#
# (c) Copyright 2018 SUSE LLC
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
module: get_ts_pkgs
author: Jack Choy
short_description: Query timestamped openstack packages installed on the system
description:
    - Goes thru each service in /opt/stack/service and returns a list of the
      timestamped venvs being used on the host.
options:
    None
'''

EXAMPLES = '''
- get_ts_pkgs:
'''


from ansible.module_utils.basic import *
from os import listdir
from os.path import basename, islink, join, realpath

SRV_DIR = '/opt/stack/service'


def main():
    ans_module = AnsibleModule(argument_spec=dict())

    # Get all the linked dirs in the service directory
    service_dirs = [join(SRV_DIR, f) for f in listdir(SRV_DIR)
                    if islink(join(SRV_DIR, f))]

    # From the linked dirs above, determine the list of timestamped packages
    ts_pkgs = sorted(set([basename(realpath(join(f, 'venv')))
                          for f in service_dirs]))
    result = dict(ts_pkgs=ts_pkgs)
    ans_module.exit_json(**result)

if __name__ == '__main__':
    main()
