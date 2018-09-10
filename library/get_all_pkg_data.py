#!/usr/bin/env python
#
# An Ansible module to query both timestamped openstack packages and
# RPM packages from SUSE-Openstack-* repos installed on the system
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
module: get_all_pkg_data
author: Jack Choy
short_description: Query timestamped openstack packages and RPM packages
from SUSE-Openstack-* repos installed on the system
description:
    - Returns a list of timestamped openstack packages and a dictionary of
      installed RPM packages from SUSE-Openstack-* repos.
options:
    None
'''

EXAMPLES = '''
- get_all_pkg_data:
'''

from ansible.module_utils.basic import *
from os import listdir
from os.path import basename, islink, join, realpath
import re
import subprocess

SRV_DIR = '/opt/stack/service'

# This regex matches all (i)nstalled packages from repos containing the name
# 'SUSE-Openstack'
re_soc_inst =  re.compile(
    r'^i\+?\s*\| '
    r'suse-openstack.* \| '
    r'(?P<pkg>\S+)\s+\| '
    r'(?P<vers>\d\S*)\s+\|',
    re.IGNORECASE)

def get_ts_pkgs():
    try:
        # Get all the linked dirs in the service directory
        service_dirs = [join(SRV_DIR, f) for f in listdir(SRV_DIR)
                        if islink(join(SRV_DIR, f))]

        # From the linked dirs above, determine the list of timestamped packages
        ts_pkgs = sorted(set([basename(realpath(join(f, 'venv')))
                              for f in service_dirs]))
        return ts_pkgs
    except Exception:
        # Something went very wrong here, so return empty list
        return []

def get_zypper_cloud_pkgs():
    try:
        output = subprocess.check_output(
            ['/usr/bin/zypper', 'packages', '--installed'])
        lines = output.split('\n')
        packages = {}
        # We put it the package information in a dict to ensure uniqueness
        # i.e. multiple repos can show >1 of the same package-version installed
        for line in lines:
            match = re.match(re_soc_inst, line)
            if match:
                packages[match.group('pkg')] = match.group('vers')

        return packages
    except Exception:
        # Something went very wrong here, so return empty list
        return {}

def main():
    packages = {}
    packages['ts_os_pkgs'] = get_ts_pkgs()
    packages['zypper_cloud_pkgs'] = get_zypper_cloud_pkgs()
    ans_module = AnsibleModule(argument_spec=dict())
    result = dict(host_pkgs = packages)
    ans_module.exit_json(**packages)

if __name__ == '__main__':
    main()
