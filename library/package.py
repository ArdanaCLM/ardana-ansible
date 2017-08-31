#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# (c) Copyright 2017 SUSE LLC
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# his program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

DOCUMENTATION = '''
---
module: package
short_description: Backport of Ansible 2.0.x 'package' module to 1.9.x
description:
    - Generic OS package manager
options:
  name:
    description:
      - Package name, or package specifier with version, like name-1.0.
        Be aware that packages are not always named the same and this module
        will not 'translate' them per distro.
    required: true
  state:
    description:
      - Whether to install (present, latest), or remove (absent) a package.
    required: true

author: Michael Tupitsyn <mtupitsyn@suse.com>
'''


EXAMPLES = '''
- name: install the latest version of ntpdate
  package:
    name: ntpdate
    state: latest

# This uses a variable as this changes per distribution.
- name: remove the apache package
  package:
    name: "{{ apache }}"
    state: absent
'''

