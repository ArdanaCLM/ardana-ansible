#!/usr/bin/python
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
#

DOCUMENTATION = '''
---
module: find_zypper_iso
short_description: Transform an ISO zypper repo to its local path
description: |
  Search for a matching zypper repository using an ISO as its source and
  transform the source into a local filesystem path.
author: SUSE Linux GmbH
options:
  name:
    description: Name of the ISO to match
'''

EXAMPLES = '''
- find_zypper_iso:
    name: SUSE-OPENSTACK-CLOUD-8
  register: cloud_iso
- debug: msg="{{ cloud_iso.path }}"
'''

import glob
import re
from urlparse import unquote


def _get_iso_uri(name):
    baseurl = None
    for repo in glob.glob('/etc/zypp/repos.d/*.repo'):
        found = False
        with open(repo) as f:
            lines = f.readlines()
            for line in lines:
                if re.search(r'^enabled\s*=\s*0$', line):
                    baseurl = None
                    found = False
                    break
                if re.search(r'^baseurl=iso:///.*%s.*$' % name, line):
                    baseurl = line.split('=', 1)[1].strip()
                    found = True
            if found:
                return baseurl
    return baseurl


def _get_file_path(iso_uri):
    iso_uri = iso_uri.replace('iso:///?iso=', '')
    if '&' in iso_uri:
        iso, dir = iso_uri.split('&')
        dir = dir.replace('url=', '')
        dir = unquote(dir).replace('dir:', '')
        return dir + '/' + iso
    return iso_uri


def main():

    argument_spec = dict(
        name=dict(type='str', required=True)
    )
    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=False)
    params = module.params

    try:
        iso_uri = _get_iso_uri(params['name'])
        if not iso_uri:
            file_path = ''
        else:
            file_path = _get_file_path(iso_uri)
    except Exception as e:
        module.fail_json(msg=e.message)
    module.exit_json(rc=0, changed=False, path=file_path)


from ansible.module_utils.basic import *


if __name__ == '__main__':
    main()
