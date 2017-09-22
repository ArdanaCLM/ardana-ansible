#!/usr/bin/python
#
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

DOCUMENTATION = '''
---
module: win_build_url
short_description: Builds the url of the windows virtualenv zip file
                   for the service specified
description:
    - The win_build_url module generates the url of the windows virtualenv
      zip file of the given service from the packager.conf file and the
      packages file. It gives the url of the latest build for a venv if
      multiple entries exist.
options:
  service:
    description:
      - The service name whose virtualenv url needs to be built.
    required: True
    aliases: []
  conf_path:
    description:
      - The path to the directory containing the packager.conf file.
    required: True
    aliases: []
  cache_path:
    description:
      - The path to the cache directory containing packages file.
    required: True
    aliases: []
author: "Usha Devulapalli"
'''

RETURN = '''
url:
    description: The url of the service virtualenv.
    type: string
    sample: "http://192.168.7.9:79/ardana-0.9.0/hyperv_venv/nova-20160101T101530Z.zip"
svc_dir:
    description: The name of the folder for the service.
    type: string
    sample: "nova-20160101T101530Z"
zip:
    description: The name of the venv zip file for the service.
    type: string
    sample: "nova-20160101T101530Z.zip"
'''

EXAMPLES = '''

  - name: building uri
    build_uri:
      service: nova
      conf_path: 'c:\Program Files\Ardana\OpenStack\etc'
      cache_path: 'c:\Program Files\Ardana\OpenStack\cache'
'''
