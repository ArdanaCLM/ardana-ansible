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

from ansible import utils

class ActionModule(object):
    '''Output custom message'''

    TRANSFERS_FILES = False

    def __init__(self, runner):
        self.runner = runner

    def run(self, conn, tmp, module_name, module_args, inject,
            complex_args=None, **kwargs):

        module = utils.template.template(self.runner.basedir,
                    '{{ansible_pkg_mgr}}', inject)
        module_return = self.runner._execute_module(conn, tmp, module,
            module_args, inject=inject, complex_args=complex_args, **kwargs)

        return module_return
