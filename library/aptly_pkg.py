#!/usr/bin/python -tt
# -*- coding: utf-8 -*-

# (c) Copyright 2016 Hewlett Packard Enterprise Development LP
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
#


def addPackage(module, name, pkg, force, remove, aptly_basecmd):
    res = {}
    res['results'] = []
    res['msg'] = ''
    res['changed'] = False
    res['rc'] = 0

    if(name and pkg):
        cmd = aptly_basecmd + ['add', name] + pkg

        # todo: if packages contain package query syntax raise error
        if(force):
            cmd.insert(1, '-force-replace=%s' % force)
        if(remove):
            cmd.insert(1, '-remove-files=%s' % remove)

        rc, out, err = module.run_command(cmd)

        res['rc'] = rc
        res['results'].append(out)
        res['msg'] = err

    return res


def removePackage(module, name, pkg, aptly_basecmd):
    res = {}
    res['results'] = []
    res['msg'] = ''
    res['changed'] = False
    res['rc'] = 0

    if(name and pkg):
        cmd = aptly_basecmd + ['remove', name] + pkg

        rc, out, err = module.run_command(cmd)

        res['rc'] = rc
        res['results'].append(out)
        res['msg'] = err

    return res


def ensure(module, name, pkg, state, force, remove):
    aptly_bin = module.get_bin_path('aptly')
    aptly_basecmd = [aptly_bin, 'repo']

    if state in ['present']:
        res = addPackage(module, name, pkg, force, remove, aptly_basecmd)
    elif state in ['absent']:
        res = removePackage(module, name, pkg, aptly_basecmd)
    else:
        module.fail_json(msg="This should never happen",
                         changed=False,
                         results='',
                         errors='unexpected state')

    return res


# todo: option to specify aptly.conf
def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(required=True),
            pkg=dict(required=True, aliases=['package', 'packages'], type="list"),
            state=dict(default='present', choices=['absent', 'present']),
            force=dict(default="no", type='bool'),
            remove=dict(default="no", type='bool')
        )
    )

    params = module.params
    name = params['name']
    pkg = [p.strip() for p in params['pkg']]
    state = params['state']
    force = params['force']
    remove = params['remove']
    results = ensure(module, name, pkg, state, force, remove)

    module.exit_json(**results)

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.urls import *
if __name__ == '__main__':
    main()
