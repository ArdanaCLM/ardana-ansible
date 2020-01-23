#!/bin/bash
#
# (c) Copyright 2020 SUSE LLC
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

# this script runs the pre-upgrade-validation playbook
PATH=/usr/bin:/bin

set -u
set -o pipefail

logfile=${HOME}/ansible-pre-upgrade-validations.log

# Check that root is not running the script
if [[ "$UID" -eq 0 ]]; then
   echo "This script should not be run as root"
   exit 1
fi

# Execute the ansible playbook for pre upgrade checks
pushd "${HOME}/scratch/ansible/next/ardana/ansible"
ansible-playbook -i hosts/verb_hosts ardana-pre-upgrade-validations.yml 2>&1 |
  tee $logfile

retval=$?

if (( ${retval:-0} != 0 )) ; then
    echo "ansible-playbook action failed. Please review $logfile to determine the cause of failure"
    exit $retval
fi

echo "$(grep "msg: Please refer to " "$logfile")"
