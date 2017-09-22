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
# This filter allows a user to test a set of packages are identical across
# a set of hosts.
#
from collections import defaultdict


def package_consistency_check(hosts, hostvars, result_attr):
    versions = defaultdict(lambda: defaultdict(list))
    for host in hosts:
        for item in hostvars[host].get(result_attr, {}).get('results', []):
            package = item.get('item', {}).get('package')
            version = item.get('stdout')
            if package is not None:
                versions[package][version].append(host)

    return {package: dict(versions[package]) for package in versions}


class FilterModule(object):

    def filters(self):
        return {'package_consistency_check': package_consistency_check}
