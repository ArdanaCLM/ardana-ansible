#
# Extends the Jinja2 test filters.
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
import jinja2.tests


def test_contained_in(thing, other):
    return thing in other


def test_contains(thing, other):
    return other in thing


jinja2.tests.TESTS['contained_in'] = test_contained_in
jinja2.tests.TESTS['contains'] = test_contains


class CallbackModule(object):
    pass
