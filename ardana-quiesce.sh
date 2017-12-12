#!/bin/bash
#
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

# this script runs the logging-test playbook to simulate service log (JSON) growth
set -eu
set -o pipefail

SCRIPT_NAME=$(basename $0)

usage() {
    echo "$SCRIPT_NAME [options]"
    echo
    echo "Quiesces OpenStack service activity on cloud controllers"
    echo
    echo "Options:"
    echo "-l, --limit <limit> -- Applies an Ansible pattern to select hosts"
    echo "                       Example: '!ardana-cp1-c1-m1' (avoids host)"
    echo "-h, --help          -- Shows this help information"
    echo
}

TEMP=$(getopt -o l:h -l limit:,help -n $SCRIPT_NAME -- "$@")
if [ $? != 0 ] ; then echo "Terminating..." >&2 ; exit 1 ; fi
echo $TEMP
# Note the quotes around `$TEMP': they are essential!
eval set -- "$TEMP"

LIMIT=""

while true ; do
    case "$1" in
        -h | --help) usage ; exit 0 ;;
        -l | --limit) LIMIT="-l $2"; shift 2 ;;
        --) shift ; break;;
        *) break ;;
    esac
done

function quiesce_simul() {
    services=("$@")
    for service in "${services[@]}"
    do
        playbook=${service}-stop.yml
        if [[ -e $playbook ]]
        then
            ansible-playbook -i hosts/verb_hosts $LIMIT $playbook &
        else
            echo "Bypassing missing playbook $playbook"
        fi
    done
    wait
}

phase_one=(
    freezer
    ceph
    ceilometer
    heat
    ironic
    designate
    cinder
    glance
    magnum
)

phase_two=(
    neutron
    nova
    octavia
    swift
)

phase_three=(
    barbican
    keystone
)

quiesce_simul "${phase_one[@]}"
quiesce_simul "${phase_two[@]}"
quiesce_simul "${phase_three[@]}"

echo "OpenStack services have now been stopped/quiesced"
