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


def createPub(module, name, prefix, component, distribution,
              force, label, origin, signing,
              from_repo, from_snapshot, aptly_basecmd):
    res = {}
    res['results'] = []
    res['msg'] = ''
    res['changed'] = False
    res['rc'] = 0

    if(name):
        if(from_repo):
            cmd = aptly_basecmd + ['repo', name]
        elif(from_snapshot):
            cmd = aptly_basecmd + ['snapshot', name]
        else:
            module.fail_json(msg="This should never happen",
                             changed=False,
                             results='',
                             errors='unexpected state')

        if(prefix):
            cmd.insert(5, prefix)
        if(component):
            cmd.insert(1, "-component=%s" % component)
        if(distribution):
            cmd.insert(1, "-distribution=%s" % distribution)
        if(force):
            cmd.insert(1, "-force-overwrite=%s" % force)
        if(label):
            cmd.insert(1, "-label=%s" % label)
        if(origin):
            cmd.insert(1, "-origin=%s" % origin)
        if(not signing):
            cmd.insert(1, "-skip-signing=%s" % (not signing))

        rc, out, err = module.run_command(cmd)

        res['rc'] = rc
        res['results'].append(out)
        res['msg'] = err

    return res


def dropPub(module, force, distribution, aptly_basecmd):
    res = {}
    res['results'] = []
    res['msg'] = ''
    res['changed'] = False
    res['rc'] = 0

    if(distribution):
        cmd = aptly_basecmd + ['drop', distribution]

        if(force):
            cmd.insert(1, "force-drop=%s" % force)

        rc, out, err = module.run_command(cmd)

        res['rc'] = rc
        res['results'].append(out)
        res['msg'] = err

    return res


def ensure(module, name, state, prefix, component,
           label, origin, force, distribution, signing,
           from_repo, from_snapshot):
    aptly_bin = module.get_bin_path('aptly')
    aptly_basecmd = [aptly_bin, 'publish']

    if state in ['present']:
        res = createPub(module, name, prefix, component, distribution,
                        force, label, origin, signing,
                        from_repo, from_snapshot, aptly_basecmd)
    elif state in ['absent']:
        res = dropPub(module, force, distribution, aptly_basecmd)
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
            prefix=dict(),
            component=dict(type="list"),
            label=dict(default=None),
            origin=dict(default=None),
            force=dict(default="no", type="bool"),
            distribution=dict(default=None),
            signing=dict(default="yes", type='bool'),
            from_repo=dict(type='bool'),
            from_snapshot=dict(type='bool')
        ),
        required_one_of=[['from_repo', 'from_snapshot']],
        mutually_exclusive=[['from_repo', 'from_snapshot']]
    )

    params = module.params
    name = params['name']
    state = params['state']
    prefix = params['prefix']
    component = params['component']
    label = params['label']
    origin = params['origin']
    force = params['force']
    distribution = params['distribution']
    signing = params['signing']
    from_repo = params['from_repo']
    from_snapshot = params['from_snapshot']
    results = ensure(module, name, state, prefix, component,
                     label, origin, force, distribution, signing,
                     from_repo, from_snapshot)

    module.exit_json(**results)

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.urls import *
if __name__ == '__main__':
    main()
