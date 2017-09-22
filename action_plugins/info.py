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

from ansible.callbacks import display
from ansible.errors import AnsibleError
from ansible.runner.return_data import ReturnData
from ansible import utils


class ActionModule(object):
    '''Output custom message'''

    TRANSFERS_FILES = False

    def __init__(self, runner):
        self.runner = runner

    def run(self, conn, tmp, module_name, module_args, inject,
            complex_args=None, **kwargs):
        args = {}
        if complex_args:
            args.update(complex_args)
        args.update(utils.parse_kv(module_args))
        if 'msg' not in args:
            raise AnsibleError("'msg' is a required argument.")

        # might be handy to allow delayed formatting
        msg = args['msg'].format(args.get('args', {}))
        display(msg, args.get('color', 'normal'))

        result = dict(
            changed=False,
            msg=msg,
        )
        return ReturnData(conn=conn, result=result)
