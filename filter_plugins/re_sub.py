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

import re


def re_sub(string='', regex='', repl='', flags='', count=1):
    flags = flags.lower()
    re_flags = 0
    if 'u' in flags:
        re_flags |= re.UNICODE
    if 'x' in flags:
        re_flags |= re.VERBOSE
    if 'l' in flags:
        re_flags |= re.LOCALE
    if 'm' in flags:
        re_flags |= re.MULTILINE
    if 's' in flags:
        re_flags |= re.DOTALL
    if 'i' in flags:
        re_flags |= re.IGNORECASE
    if 'g' in flags:
        count = 0

    return re.sub(regex, repl, string, flags=re_flags, count=count)


class FilterModule(object):
    def filters(self):
        return {
            're_sub': re_sub
        }
