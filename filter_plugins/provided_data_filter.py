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
import jinja2.runtime as jrt


#
# provided_data filter:
#
# Sample usage:
# Return the list of 'mechanism_drivers' parameters provided to the
# neutron-ml2-plugin (NEU-ML2) service.
#
#    {{ NEU_ML2 | provided_data('mechanism_drivers') }}
#
def provided_data(grp, option, default=[]):
    value_list = []
    try:
        for pd in grp.get('provided_data', []):
            for pdd in pd.get('data', []):
                if pdd.get('option', '') == option:
                    value_list.extend(pdd.get('values', []))
    except (jrt.UndefinedError, AttributeError):
        return default
    return value_list


def test_provided_data():
    input = {'provided_data': [{'data': [{'option': 'pet',
                                          'values': ['dog', 'cat']},
                                         {'option': 'flowers',
                                          'values': ['iris']}],
                                'provided_by': 'SVC1'},
                               {'data': [{'option': 'pet',
                                          'values': ['turtle']}],
                                'provided_by': 'SVC2'}]}

    expected = ['dog', 'cat', 'turtle']
    assert set(provided_data(input, 'pet')) == set(expected)
    assert provided_data(input, 'flowers') == ['iris']
    assert provided_data('string', 'pet') == []
    assert provided_data(
        'string', 'pet', default=['undefined']) == ['undefined']


class FilterModule(object):
    def filters(self):
        return {
            'provided_data': provided_data
        }


if __name__ == "__main__":
    test_provided_data()
