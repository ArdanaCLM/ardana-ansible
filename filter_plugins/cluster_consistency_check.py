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
# This filter allows a user to get the control plane names as a set for the
# current play hosts. if host details do not exit in hostvar we skip the
# entry. For example this would be skipped for localhost
#

def cluster_consistency_check(hosts, hostvars):
    control_plane_names = {
        hostvars[host]['host']['my_dimensions']['control_plane']
        for host in hosts
        if 'host' in hostvars[host]
        }

    return list(control_plane_names)


class FilterModule(object):

    def filters(self):
        return {'cluster_consistency_check': cluster_consistency_check}
