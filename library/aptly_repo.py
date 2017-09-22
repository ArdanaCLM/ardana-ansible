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


def repoExists(module, name, aptly_basecmd):
    cmd = aptly_basecmd + ['show', name]
    rc, out, err = module.run_command(cmd)
    msgs = [out, err]
    if any("local repo with name %s not found" % name in s for s in msgs):
        return False
    elif(rc is 0):
        # repo already exists
        return True
    else:
        # unknown error
        module.fail_json(msg='The following error occured: %s' % err)


def createRepo(module, name, comment, component, distribution, aptly_basecmd):
    res = {}
    res['results'] = []
    res['msg'] = ''
    res['changed'] = False
    res['rc'] = 0

    if(name):
        if repoExists(module, name, aptly_basecmd):
            res['results'] = "Repo %s already exists." % name
            return res

        cmd = aptly_basecmd + ['create', name]

        if(comment):
            cmd.insert(1, '-comment=%s' % comment)
        if(component):
            cmd.insert(1, '-component=%s' % component)
        if(distribution):
            cmd.insert(1, '-distribution=%s' % distribution)

        rc, out, err = module.run_command(cmd)

        res['rc'] = rc
        res['results'].append(out)
        res['msg'] += err

    return res


def dropRepo(module, name, force, aptly_basecmd):
    res = {}
    res['results'] = []
    res['msg'] = ''
    res['changed'] = False
    res['rc'] = 0

    if(name):
        cmd = aptly_basecmd + ['drop', name]

        if(force):
            cmd += ['-force' + force]

        rc, out, err = module.run_command(cmd)

        res['rc'] = rc
        res['results'].append(out)
        res['msg'] += err

    return res


def ensure(module, name, state, comment, component, distribution, force):
    aptly_bin = module.get_bin_path('aptly')
    aptly_basecmd = [aptly_bin, 'repo']

    if state in ['present']:
        res = createRepo(module, name, comment, component,
                         distribution, aptly_basecmd)
    elif state in ['absent']:
        res = dropRepo(module, name, force, aptly_basecmd)
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
            state=dict(default="present", choices=["absent", "present"]),
            comment=dict(default=""),
            component=dict(default=""),
            distribution=dict(default=""),
            force=dict(default="no", type='bool')
        )
    )

    params = module.params
    name = params['name']
    state = params['state']
    comment = params['comment']
    component = params['component']
    distribution = params['distribution']
    force = params['force']
    results = ensure(module, name, state, comment,
                     component, distribution, force)

    module.exit_json(**results)

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.urls import *
if __name__ == '__main__':
    main()
