#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# (c) Copyright 2016 Hewlett Packard Enterprise Development LP
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

Documentation = '''
---
module: info
short_description: Output a custom message with formatting
description:
    - This module allows outputting of information messages to allow
      instructions and help to be provided by playbooks for users to
      check in a sensible format.
options:
  msg:
    description:
      - The customized message used for the warning message.
    required: true

author: Darragh Bailey
'''


EXAMPLES = '''
# Example playbook using warning
- info: msg="The available options to be executed:\n\t-1 option one."
'''

