#
# (c) Copyright 2015 Hewlett Packard Enterprise Development LP
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

import imp
import os.path


path = os.path.dirname(os.path.realpath(__file__))

ardanaencrypt = imp.load_source('ardanaencrypt', path + '/../ardanaencrypt.py')

encryption_class = 'openssl'

ardanaencrypt_class = getattr(ardanaencrypt, encryption_class)


def openstack_user_password_decrypt(value, *args, **kw):
    prefix = None
    if value.startswith(ardanaencrypt_class.prefix):
        prefix = ardanaencrypt_class.prefix
    # For upgrade cases, need to support existing encrypted values which may
    # have legacy prefix in-use.
    elif value.startswith(ardanaencrypt_class.legacy_prefix):
        prefix = ardanaencrypt_class.legacy_prefix

    if prefix is None:
        return value
    else:
        obj = ardanaencrypt_class()
        return obj.decrypt(value[len(prefix):])


class FilterModule(object):
    def filters(self):
        return {'openstack_user_password_decrypt':
                openstack_user_password_decrypt}
