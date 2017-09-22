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


def createSnapshot(module, name, repo, empty, aptly_basecmd):
    res = {}
    res['results'] = []
    res['msg'] = ''
    res['changed'] = False
    res['rc'] = 0

    if(name and repo):
        cmd = aptly_basecmd + ['create', name, 'from', 'repo', repo]

        # todo: error if repo does not exist
        rc, out, err = module.run_command(cmd)

        res['rc'] = rc
        res['results'].append(out)
        res['msg'] = err
    elif(empty):
        cmd = aptly_basecmd + ['create', name, 'empty']

        # todo: error if repo does not exist
        rc, out, err = module.run_command(cmd)

        res['rc'] = rc
        res['results'].append(out)
        res['msg'] = err

    return res


def dropSnapshot(module, name, force, aptly_basecmd):
    res = {}
    res['results'] = []
    res['msg'] = ''
    res['changed'] = False
    res['rc'] = 0

    if(name):
        cmd = aptly_basecmd + ['drop', name]

        # todo: error if repo does not exist
        if(force):
            cmd.insert(1, '-force=%s' % force)

        rc, out, err = module.run_command(cmd)

        res['rc'] = rc
        res['results'].append(out)
        res['msg'] = err

    return res


def ensure(module, name, state, repo, force, empty):
    aptly_bin = module.get_bin_path('aptly')
    aptly_basecmd = [aptly_bin, 'snapshot']

    if state in ['present']:
        res = createSnapshot(module, name, repo, empty, aptly_basecmd)
    elif state in ['absent']:
        res = dropSnapshot(module, name, force, aptly_basecmd)
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
            state=dict(default='present', choices=['absent', 'present']),
            repo=dict(aliases=['repo_name']),
            force=dict(default="no", type='bool'),
            empty=dict(default="no", type='bool')
        ),
        required_one_of=[['repo', 'empty']],
        mutually_exclusive=[['repo', 'empty']],
    )

    params = module.params
    name = params['name']
    state = params['state']
    repo = params['repo']
    force = params['force']
    empty = params['empty']

    results = ensure(module, name, state, repo, force, empty)

    module.exit_json(**results)

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.urls import *
if __name__ == '__main__':
    main()
