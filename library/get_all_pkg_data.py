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


def get_ts_pkgs():
    try:
        # Get all the linked dirs in the service directory
        service_dirs = [join(SRV_DIR, f) for f in listdir(SRV_DIR)
                        if islink(join(SRV_DIR, f))]

        # From the linked dirs above,
        # determine the list of timestamped packages
        ts_pkgs = sorted(set([basename(realpath(join(f, 'venv')))
                              for f in service_dirs]))
        return ts_pkgs
    except Exception:
        # Something went very wrong here, so return empty list
        return []


def get_zypper_cloud_pkgs():
    try:
        # find the repo that the ardana package was installed from
        output = subprocess.check_output(
            ['/usr/bin/zypper', 'info', '-t', 'package', 'ardana'])
        lines = output.split('\n')
        # parse the name out of the zypper output
        for line in lines:
            if line.startswith('Repository'):
                repo = line.split(':')[1].strip()
                break

        # look for all packages installed from the same repo as ardanaservice
        output = subprocess.check_output(
             ['/usr/bin/zypper', 'packages', '--installed', '--repo', repo])
        lines = output.split('\n')
        packages = {}
        # We put it the package information in a dict to ensure uniqueness
        # i.e. multiple repos can show >1 of the same package-version installed
        # the regex is parsing the output into groups, the match condition is
        # universal now
        for line in lines:
            if('|' not in line):
                continue
            fields = line.split('|')
            pkg = fields[2].strip()
            vers = fields[3].strip()
            if('Name' != pkg and 'Version' != vers):
                packages[pkg] = vers

        return packages
    except Exception:
        # Something went very wrong here, so return empty list
        return {}


def main():
    packages = {}
    packages['ts_os_pkgs'] = get_ts_pkgs()
    packages['zypper_cloud_pkgs'] = get_zypper_cloud_pkgs()
    ans_module = AnsibleModule(argument_spec=dict())
    result = dict(host_pkgs=packages)
    ans_module.exit_json(**packages)

if __name__ == '__main__':
    main()
