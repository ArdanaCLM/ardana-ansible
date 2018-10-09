#!/usr/bin/python
# -*- coding: utf-8 -*-

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
module: birdseyeview
version_added: "1.9"
short_description: Generate a bird's eye view summary
description:
  This module generates a bird's eye view of an existing installation to help
  facilitate the initial contact with our Support, Consulting, and/or Training
  departments.
options:
    action:
        required: true
        description:
          - The action to be performed
    src:
        required: true
        description:
          - The absolute path to the directory containing remotely fetched
            files
    dest:
        required: false
        description:
          - The name of the file. If a relative name is provided, the absolute
            path to the ".../my_cloud/info" directory will be prepended to make
            it absolute.
    format:
        required: false
        description:
          - The format of the output file. If no value provided, it will
            attempt to determine based on dest extension else it will use the
            default value.
'''

EXAMPLES = '''
- birdseyeview:
    action: list_cinder_config_files
    src: /tmp/my_birdseyeview
    register: cinder_files

- birdseyeview:
    action: generate_summary
    src: /tmp/my_birdseyeview
    dest: /tmp/birdseyeview.yml
'''

import json
import os
import re
import string
import sys
import yaml

from six.moves import configparser

# import module snippets
from ansible.module_utils.basic import *


def get_config_parser():
    if sys.version_info >= (3, 2):
        return configparser.ConfigParser()
    return configparser.SafeConfigParser()


class ServerDetails(object):
    def __init__(self, src_dir):
        self.src_dir = src_dir

    def get_hostname(self):
        with open(os.path.join(self.src_dir, 'hostname')) as f:
            return f.read().strip()

    def get_mac_addresses(self):
        mac_addrs = {}

        pattern = re.compile(
            'link/ether {0} '.format(string.join(6 * ('[a-z0-9][a-z0-9]',), ':'))
        )
        with open(os.path.join(self.src_dir, 'ipa')) as f:
            for line in f.readlines():
                s = pattern.search(line.lower())
                if s:
                    mac_addrs[s.group(0).split(' ')[1]] = True

        return mac_addrs.keys()

    def get_hardware_details(self):
        ret = {}

        values = [
            'Manufacturer',
            'Family',
            'Product Name',
            'Version',
        ]
        with open(os.path.join(self.src_dir, 'dmidecode')) as f:
            for line in f.readlines():
                line = line.strip()
                if line:
                    tokens = line.strip().split(': ', 1)
                    if len(tokens) > 1 and tokens[0] in values:
                        ret[tokens[0]] = tokens[1]

        return ret

    def get_os_details(self):
        ret = {}

        values = [
            'NAME',
            'VERSION',
        ]
        with open(os.path.join(self.src_dir, 'os-release')) as f:
            for line in f.readlines():
                line = line.strip()
                if line and not line.startswith('#'):
                    tokens = line.strip().split('=', 1)
                    if len(tokens) > 1 and tokens[0] in values:
                        ret[tokens[0]] = tokens[1].strip('\'"')

        return ret


class Service(object):

    def __init__(self, src_dir):
        self.src_dir = src_dir

        # the following variables are populated by subclass
        self.services = []

    # extract filenames from systemd files
    def list_config_files(self):
        files = dict()

        for service in self.services:
            fn = os.path.join(self.src_dir, '{0}.service'.format(service))
            if not os.path.exists(fn):
                continue

            cfgparser = get_config_parser()
            with open(fn) as f:
                cfgparser.readfp(f)

            if not cfgparser.has_section('Service') or \
                    not cfgparser.has_option('Service', 'ExecStart'):
                continue

            i = 0
            params = cfgparser.get('Service', 'ExecStart').split(' ')
            while i < len(params):
                if params[i] == '--config-file':
                    i += 1
                    files[params[i]] = True
                i += 1

        return files.keys()


class CinderService(Service):
    def __init__(self, src_dir):
        super(CinderService, self).__init__(src_dir)

        self.services = [
            'cinder-api'
        ]

    # roles/_CND-CMN/templates/cinder.conf.j2
    # [DEFAULT]
    # enabled_backends=3par_iscsi,3par_iscsi2
    # volume_driver=cinder.volume.drivers.eqlx.DellEQLSanISCSIDriver
    # [3par_iscsi2]
    # volume_driver=cinder.volume.drivers.san.hp.hp_3par_iscsi.HP3PARISCSIDriver
    # [3par_iscsi]
    # volume_driver=cinder.volume.drivers.san.hp.hp_3par_iscsi.HP3PARISCSIDriver
    def birdseye(self):
        conf = dict()

        fn = os.path.join(self.src_dir, 'cinder.conf')
        if not os.path.exists(fn):
            return conf

        cfgparser = get_config_parser()
        with open(fn) as f:
            cfgparser.readfp(f)

        # DEFAULT section
        conf['DEFAULT'] = dict()
        try:
            conf['DEFAULT']['volume_driver'] = \
                cfgparser.get('DEFAULT', 'volume_driver')
        except:
            pass

        # backends
        enabled_backends = None
        try:
            enabled_backends = cfgparser.get('DEFAULT', 'enabled_backends')
        except:
            pass
        if enabled_backends:
            conf['DEFAULT']['enabled_backends'] = enabled_backends

            conf['enabled_backends'] = dict()
            for backend in enabled_backends.split(','):
                # skip blanks
                if not backend:
                    continue

                tmp = dict()
                conf['enabled_backends'][backend] = tmp
                try:
                    tmp['volume_driver'] = \
                        cfgparser.get(backend, 'volume_driver')
                except:
                    pass

        return conf


class GlanceService(Service):
    def __init__(self, src_dir):
        super(GlanceService, self).__init__(src_dir)

        self.services = [
            'glance-api'
        ]

    # roles/GLA-API/templates/glance-api.conf.j2
    # # List of stores enabled. Valid stores are:
    # # cinder
    # # file
    # # http
    # # rbd
    # # sheepdog
    # # swift
    # # vsphere
    # [glance_store]
    # stores = file,http,vsphere
    # default_store = vsphere
    def birdseye(self):
        conf = dict()

        fn = os.path.join(self.src_dir, 'glance-api.conf')
        if not os.path.exists(fn):
            return conf

        cfgparser = get_config_parser()
        with open(fn) as f:
            cfgparser.readfp(f)

        if not cfgparser.has_section('glance_store'):
            return conf

        conf['glance_store'] = dict()

        try:
            conf['glance_store']['stores'] = \
                cfgparser.get('glance_store', 'stores').split(',')
        except:
            pass

        try:
            conf['glance_store']['default_store'] = \
                cfgparser.get('glance_store', 'default_store')
        except:
            pass

        return conf


class BirdsEyeView(object):

    @staticmethod
    def format_choices():
        return ['json', 'yaml']

    @staticmethod
    def format_default():
        return 'yaml'

    def __init__(self, mycloud_dir, src_dir):
        self.mycloud_dir = mycloud_dir
        self.src_dir = src_dir

        self.definition_cache = dict()

    def _dir_to_array(self, path):
        ret = []

        files = []
        for fn in sorted(os.listdir(path)):
            absfile = os.path.join(path, fn)
            if os.path.isdir(absfile):
                ret.append({
                    fn: self._dir_to_array(absfile)
                })
            else:
                files.append(fn)

        ret.extend(files)

        return ret

    def _load_definition_file(self, path, reload_file=False):
        if not reload_file and path in self.definition_cache:
            return

        fn = os.path.join(self.mycloud_dir, 'definition/data', path)
        with open(fn, 'r') as f:
            self.definition_cache[path] = yaml.load(f)

    def _product_info(self):
        info = {}

        for fn in [
            '/etc/HPE_Helion_version',
            '/etc/Ardana_version',
        ]:
            if os.path.exists(fn):
                version = []
                with open(fn, 'r') as f:
                    for line in f.readlines():
                        if not line.startswith('#'):
                            version.append(line.strip())
                info['version'] = version
                break

        return info

    def _servers_details(self):
        nodes = []

        nodes_path = os.path.join(self.src_dir, 'nodes')
        for fn in sorted(os.listdir(nodes_path)):
            absfile = os.path.join(nodes_path, fn)
            if os.path.isdir(absfile):
                nodes.append(ServerDetails(absfile))

        return nodes

    # TODO: commented server properties below exist in the CP modeling data
    # but not [easily] in the definition files
    def _servers_definitions(self):
        self._load_definition_file('servers.yml')

        servers = {}
        tmp = self.definition_cache['servers.yml']['servers']
        for server in tmp:
            servers[server['id']] = {
                'mac-addr': server['mac-addr'],
                # 'name': server['name'],
                # 'control_plane': server['control-plane-name'],
                # 'failure_zone': server['failure-zone'],
                'group': server['server-group'],
                'role': server['role'],
                # 'state' : server['state'],
            }
        return servers

    def _servers(self):
        definitions = self._servers_definitions()
        details = self._servers_details()

        # merge the two structures, join by MAC address
        for name, definition in definitions.iteritems():
            # security: do not share MAC address?
            mac_addr = definition.pop('mac-addr')
            for detail in details:
                if mac_addr in detail.get_mac_addresses():
                    # security: do not share hostname?
                    # definition['hostname'] = detail.get_hostname()
                    definition['hardware'] = detail.get_hardware_details()
                    definition['operating_system'] = detail.get_os_details()
                    break

        return definitions

    def _services(self):
        self._load_definition_file('something.yml')

        services = {}
        tmp = self.definition_cache['something.yml']['services']
        for name, value in tmp:
            service = {}
            services[name] = service
            if 'component-list' in value:
                service['component_list'] = value['component-list']
        return services

    def _control_planes(self):
        self._load_definition_file('control_plane.yml')

        control_planes = {}
        tmp = self.definition_cache['control_plane.yml']['control-planes']
        for plane in tmp:
            clusters = {}
            control_planes[plane['name']] = {
                'clusters': clusters,
            }

            for cluster in plane['clusters']:
                service_components = []
                clusters[cluster['name']] = {
                    'server_roles': cluster['server-role'],
                    'service_components': service_components,
                }

                for component in sorted(cluster['service-components']):
                    service_components.append(component)

        return control_planes

    def _third_party(self):
        return {
            'files': {
                '~/third-party':
                    self._dir_to_array(os.path.expanduser('~/third-party'))
            }
        }

    def _cinder_storage(self):
        return CinderService(self.src_dir).birdseye()

    def _glance_storage(self):
        return GlanceService(self.src_dir).birdseye()

    def generate(self):
        data = dict()
        data['product'] = self._product_info()
        data['servers'] = self._servers()
        # TODO: commented services below exist in the CP modeling data
        # but not [easily] in the definition files
        # data['services'] = self._services()
        data['control_planes'] = self._control_planes()
        data['thirdparty'] = self._third_party()
        data['cinder'] = self._cinder_storage()
        data['glance'] = self._glance_storage()
        return data


def action_list_cinder_config_files(module):
    return {
        'changed': False,
        'files': CinderService(module.params['src']).list_config_files(),
    }


def action_list_glance_config_files(module):
    return {
        'changed': False,
        'files': GlanceService(module.params['src']).list_config_files(),
    }


def action_generate(module):
    src = module.params['src']
    dest = module.params['dest']
    fformat = module.params['format']

    # determine format
    # order of precedence is:
    #   explicitly
    #   by extension
    #   default value
    if not fformat:
        # extract and lower file extension
        (root, ext) = os.path.splitext(dest)
        ext = ext[1:].lower()

        # handle abbreviations
        if ext == 'yml':
            ext = 'yaml'

        # find matching format
        if ext in BirdsEyeView.format_choices():
            fformat = ext
        else:
            fformat = BirdsEyeView.format_default()

    # find my_cloud source directory
    mycloud_dir = None
    for p in [
        # HOS
        '~/helion/my_cloud',
        # Ardana
        '~/openstack/my_cloud',
    ]:
        p = os.path.expanduser(p)
        if os.path.exists(p):
            mycloud_dir = p
            break
    if not mycloud_dir:
        raise Exception('Unable to find directory "my_cloud"')

    # generate summary
    data = BirdsEyeView(mycloud_dir, src).generate()

    # ensure an absolute output filename
    if not dest.startswith(os.sep):
        dest = os.path.join(mycloud_dir, 'info', dest)

    # write summary
    with open(dest, 'wb') as f:
        if fformat == 'json':
            json.dump(data, f)
        elif fformat == 'yaml':
            yaml.dump(data, f, default_flow_style=False)

    return {
        'changed': True,
        'file': dest,
    }


def main():
    module = AnsibleModule(
        argument_spec=dict(
            action=dict(
                required=True,
                choices=[
                    'list_cinder_config_files',
                    'list_glance_config_files',
                    'generate_summary',
                ],
                type='str'
            ),
            src=dict(required=True, type='str'),
            dest=dict(required=False, type='str'),
            format=dict(
                required=False,
                choices=BirdsEyeView.format_choices(),
                default=None,
                type='str'
            )
        )
    )

    ret = dict()
    action = module.params['action']
    if action == 'list_cinder_config_files':
        ret = action_list_cinder_config_files(module)
    elif action == 'list_glance_config_files':
        ret = action_list_glance_config_files(module)
    elif action == 'generate_summary':
        ret = action_generate(module)

    # exit module
    module.exit_json(**ret)


main()
