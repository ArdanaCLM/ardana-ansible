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

ardana_encrypt = imp.load_source(
    'ardanaencrypt', path + '/../ardanaencrypt.py')

encryption_class = 'openssl'

ardanaencrypt_class = getattr(ardana_encrypt, encryption_class)

ENCRYPT_KEY_NAME = 'ARDANA_USER_PASSWORD_ENCRYPT_KEY'
LEGACY_KEY_NAME = 'HOS_USER_PASSWORD_ENCRYPT_KEY'


def openstack_user_password_encrypt(value, key=None, *args, **kw):
    # If a key is supplied to the filter, use it. Make sure
    # we stash any existing key value in the environment,
    # as os.environ() changes will persist.
    key_stash = None

    def _get_legacy_value():
        if LEGACY_KEY_NAME in os.environ:
            value = os.environ[LEGACY_KEY_NAME]
            del os.environ[LEGACY_KEY_NAME]
            return value

    def _backup_env_key():
        legacy_value = _get_legacy_value()
        if legacy_value or legacy_value == "":
            key_stash = legacy_value
        elif ENCRYPT_KEY_NAME in os.environ:
            key_stash = os.environ(ENCRYPT_KEY_NAME)
        os.environ[ENCRYPT_KEY_NAME] = key

    def _restore_env_key():
        # Restore the stashed key
        if key_stash is None:
            if LEGACY_KEY_NAME in os.environ:
                del os.environ[LEGACY_KEY_NAME]
            del os.environ[ENCRYPT_KEY_NAME]
        else:
            os.environ[ENCRYPT_KEY_NAME] = key_stash

    if key is not None:
        _backup_env_key()

    if (ENCRYPT_KEY_NAME not in os.environ and
            LEGACY_KEY_NAME not in os.environ):
        return value

    if (os.environ[ENCRYPT_KEY_NAME] is None
            or os.environ[ENCRYPT_KEY_NAME] == ""):
        _restore_env_key()
        return value

    obj = ardanaencrypt_class()
    result = obj.prefix + obj.encrypt(value)

    _restore_env_key()

    return result


class FilterModule(object):
    def filters(self):
        return {'openstack_user_password_encrypt':
                openstack_user_password_encrypt}
