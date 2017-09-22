#
# (c) Copyright 2015-2016 Hewlett Packard Enterprise Development LP
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
# Load a "packages" manifest from a directory; cache these
# by default.

# Given such a dictionary, locate the latest version of a
# named package.


import six
import yaml

# J2 expressions are repeatedly re-evaluated.
# Often, we want to access a fixed file on disk.
# So, we cache results on a per-directory basis.

_packages = {}


def load_packages(manifest_loc, cached=True):
    if cached and manifest_loc in _packages:
        return _packages[manifest_loc]

    try:
        with open(manifest_loc) as f:
            manifest = yaml.safe_load(f)
    except IOError:
        # The file might turn up later - don't cache this result.
        return None

    if cached:
        _packages[manifest_loc] = manifest

    return manifest


def parse_version(v_str):
    """Convert a string representation of a version into a comparable tuple"""

    return [[int(n) if n.isdigit() else n for n in p.split('.')]
            for p in v_str.split(':')]


def package_max_version(manifest, package):
    packages = manifest['packages']
    if package in packages:
        return max(packages[package], key=parse_version)


def package_max_unpatched_version(manifest, package):
    """Find the base version of the latest unpatched venv"""
    packages = manifest['packages']
    if package in packages:
        max_version = None
        max_v_str = None
        for v in packages[package]:
            version = parse_version(v)
            # Unpatched version?
            if len(version) > 2:
                # Nope
                continue
            if max_version is not None and max_version > version:
                continue
            max_version = version
            max_v_str = v
        return max_v_str


def package_next_patch_number(manifest, package, base_v_str):
    """Find the next patch number available for a given venv

       This will be 1, if no patched version exists,
       1 more than the highest patch value if a patched version is
       found,
       and None if there is no venv that has the same upstream
       patch value as the base_version"""

    packages = manifest['packages']
    base_version = parse_version(base_v_str)

    if package in packages:
        max_version = None
        for v in packages[package]:
            version = parse_version(v)

            # Unpatched version?
            if len(version) <= 2:
                # Yes!
                # Check if this is the only matching version
                if max_version is None and version[:2] == base_version[:2]:
                    # If so, remember it
                    max_version = version
                continue

            # Upstream parts of the verison match?
            if version[:2] != base_version[:2]:
                continue  # Nope

            # Remember highest patch number
            if max_version is not None and max_version > version:
                continue
            max_version = version

        # Did we find any suitable version at all?
        if max_version is None:
            return None  # Nope

        # Did we find a patched version?
        if len(max_version) <= 2:
            return 1  # Nope

        # Return the next available patch number
        try:
            return max_version[2][0] + 1
        except TypeError:
            return 1


def package_get_details(manifest, package, v_str):
    """Return the manifest details for a given version of a package.

       This is just a dictionary access - however, we abstract it away
       behind this filter.
    """

    try:
        return manifest['packages'][package][v_str]
    except KeyError:
        return None


# Return a predictable path to the configuration directory
# or the binary directory for a service component.

# This relies on the service component being "activated" -
# that is, having an unversioned symlink in /opt/stack/service
# pointing to the current version.

# We might have an old string 'version' - which acts as a suffix -
# or a dictionary of .version, .suffix, .v=1

def suffix(version):
    if isinstance(version, six.string_types):
        return version

    # We have a structured return value.
    assert isinstance(version, dict)
    assert version['v'] == 1
    return version['suffix']


def venv_dir(component, version=None):
    if version is None:
        return ("/opt/stack/service/{component}/venv"
                .format(component=component))
    return ("/opt/stack/service/{component}-{suffix}/venv"
            .format(component=component, suffix=suffix(version)))


def config_dir(component, version=None):
    if version is None:
        return ("/opt/stack/service/{component}/etc"
                .format(component=component))
    return ("/opt/stack/service/{component}-{suffix}/etc"
            .format(component=component, suffix=suffix(version)))


def bin_dir(component, version=None):
    if version is None:
        return ("/opt/stack/service/{component}/venv/bin"
                .format(component=component))
    return ("/opt/stack/service/{component}-{suffix}/venv/bin"
            .format(component=component, suffix=suffix(version)))


def share_dir(component, version=None):
    if version is None:
        return ("/opt/stack/service/{component}/venv/share"
                .format(component=component))
    return ("/opt/stack/service/{component}-{suffix}/venv/share"
            .format(component=component, suffix=suffix(version)))


def jar_dir(component, version=None):
    if version is None:
        return ("/opt/stack/service/{component}/venv/lib"
                .format(component=component))
    return ("/opt/stack/service/{component}-{suffix}/venv/lib"
            .format(component=component, suffix=suffix(version)))


class FilterModule(object):

    def filters(self):
        return {'venv_dir': venv_dir,
                'config_dir': config_dir,
                'bin_dir': bin_dir,
                'share_dir': share_dir,
                'jar_dir': jar_dir,
                'load_packages': load_packages,
                'package_max_version': package_max_version,
                'package_max_unpatched_version': package_max_unpatched_version,
                'package_next_patch_number': package_next_patch_number,
                'package_get_details': package_get_details,
                }
