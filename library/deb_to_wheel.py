#!/usr/bin/python
# -*- coding: utf-8 -*-
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

"""deb to wheel ansible module."""

import wheel.bdist_wheel
import tempfile
from email.message import Message
from wheel.pkginfo import read_pkg_info, write_pkg_info
from wheel.archive import archive_wheelfile
from email.parser import Parser
import shutil
import debian.debfile
import glob
import distutils
import os
import re

DOCUMENTATION = '''
---
module: deb_to_wheel
short_description: Module for translating deb-packaged python code to a wheel.
description:
    - Ansible module for translating python code packaged as a debian to
    - a python wheel.
author: "Seamus Delaney"
requirements:
    - debian
options:
    src:
        description:
            - The debian package we want to translate to a wheel.
        required: true
    dest:
        description:
            - The location for the produced wheel.
        required: false
        default: null
'''

EXAMPLES = '''
- deb_to_wheel:
    src: /home/debian/my_deb.deb
    dest: /home/debian/my_wheel.whl
'''


def read_control(path):
    """Parse debian package control metadata."""
    with open(path, "r") as headers:
        message = Parser().parse(headers)
    return message


def control_to_metadata(control_dir, wheel_dir):
    """Convert deb control to METADATA file."""
    ctrl_info = read_control(control_dir)
    pkg_name = ctrl_info['Package'].replace('-', '_')
    pkg_version = re.search(r'\d.*', ctrl_info['Version'].replace('-', '_'))
    pkg_string = "%s-%s" % (pkg_name, pkg_version)

    metadata = Message()
    metadata.add_header('Metadata-Version', '2.0')
    metadata['Name'] = ctrl_info['Package']
    metadata['Version'] = pkg_version
    metadata['Home-page'] = ctrl_info['Homepage']

    # get maintainer name and email
    maintainer_pattern = r'\s*(?P<maintainer>.*?)\s*?\<(?P<m_email>.*?)\>'
    re_results = re.search(maintainer_pattern, ctrl_info['Maintainer'])
    metadata['Author'] = re_results.group('maintainer')
    metadata['Author-email'] = re_results.group('m_email')

    metadata['Summary'] = ctrl_info['Description'].split('\n', 1)[0]
    metadata['Description'] = ctrl_info['Description']

    # Write wheelfile
    dist_info_dir = wheel_dir + "/" + pkg_string + ".dist-info"
    os.mkdir(dist_info_dir)
    metadata_path = os.path.join(dist_info_dir, 'METADATA')
    write_pkg_info(metadata_path, metadata)

    return(pkg_name, pkg_version)


def read_egg_metadata(path):
    """Return a dict representing egg metadata."""
    if os.path.isfile(path):
        pkg_info = read_pkg_info(path)
    else:
        pkginfo_path = os.path.join(path, 'PKG-INFO')
        pkg_info = read_pkg_info(pkginfo_path)

    return pkg_info


def egg_to_metadata(module, egg_path, wheel_dir):
    """Convert egg data to METADATA."""
    pkg_info = read_egg_metadata(egg_path)
    pkg_name = pkg_info['Name'].replace('-', '_')
    pkg_version_regex = re.search(r'\d.*',
                                  pkg_info['Version'].replace('-', '_'))
    if pkg_version_regex is None:
        module.fail_json(
            msg="Error: Version string does not comply with PEP440.")
    pkg_version = pkg_version_regex.group(0)

    pkg_string = "%s-%s" % (pkg_name, pkg_version)

    dist_info_dir = wheel_dir + "/" + pkg_string + ".dist-info"
    bw = wheel.bdist_wheel.bdist_wheel(distutils.dist.Distribution())
    bw.egg2dist(egg_path, dist_info_dir)

    return(pkg_name, pkg_version)


def extract_deb(src, dest):
    """Extract deb package content to specified destination."""
    deb = debian.debfile.DebFile(src)

    deb_data = deb.data.tgz()
    deb_data.extractall(path=dest)

    deb_ctrl = deb.control.tgz()
    deb_ctrl.extractall(path=dest + "/DEBIAN")


def cleanup(*scratch_dirs):
    """Remove any directories passed to the function."""
    for dir in scratch_dirs:
        shutil.rmtree(dir)


def copytree(src, dst, symlinks=False, ignore=None):
    """shutil.copytree workaround for copying into an existing directory."""
    names = os.listdir(src)
    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    if(not os.path.exists(dst)):
        os.makedirs(dst)
    errors = []
    for name in names:
        if name in ignored_names:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                copytree(srcname, dstname, symlinks, ignore)
            else:
                # Will raise a SpecialFileError for unsupported file types
                shutil.copy2(srcname, dstname)
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except Error, err:
            errors.extend(err.args[0])
        except EnvironmentError, why:
            errors.append((srcname, dstname, str(why)))
    try:
        shutil.copystat(src, dst)
    except OSError, why:
        errors.append((src, dst, str(why)))
    if errors:
        raise shutil.Error, errors


def deb_to_wheel(module, src, dest):
    """Translate a debian package to a python wheel."""
    res = {}
    res['results'] = []
    res['msg'] = ''
    res['changed'] = False
    res['rc'] = 1

    # Create scratch directories
    temp_deb_dir = tempfile.mkdtemp()
    temp_wheel_dir = tempfile.mkdtemp()

    # Extract deb package content to scratch directory
    extract_deb(src, temp_deb_dir)

    # Check if there's an egg file or directory
    egg_path = glob.glob(temp_deb_dir +
                         "/usr/lib/python2.7/dist-packages/*.egg-info")
    if len(egg_path) != 0:
        egg_path = egg_path[0]
        pkg_name, pkg_version = egg_to_metadata(module,
                                                egg_path,
                                                temp_wheel_dir)
    else:
        # Convert deb control to METADATA file
        control_dir = os.path.join(temp_deb_dir, "DEBIAN/control")
        pkg_name, pkg_version = control_to_metadata(control_dir,
                                                    temp_wheel_dir)

    # How directories in the debian package should be translated to the wheel
    pkg_string = "%s-%s" % (pkg_name, pkg_version)
    data_dir = os.path.join(temp_wheel_dir, pkg_string + ".data")
    dir_map = {
        'usr/lib/python2.7/dist-packages': temp_wheel_dir,
        'usr/bin': os.path.join(data_dir, 'scripts'),
        'usr/include/python2.7/' + pkg_name: os.path.join(data_dir, 'headers'),
        'usr': os.path.join(data_dir, 'data')
    }

    for source, destination in dir_map.iteritems():
        if(os.path.exists(os.path.join(temp_deb_dir, source))):
            ignore = []
            if(source is 'usr'):
                ignore = ['lib', 'bin', 'include']
            copytree(
                os.path.join(temp_deb_dir, source),
                destination,
                ignore=shutil.ignore_patterns(*ignore)
            )

    # Write out record and wheelfile
    dist_info_dir = temp_wheel_dir + "/" + pkg_string + ".dist-info"
    bw = wheel.bdist_wheel.bdist_wheel(distutils.dist.Distribution())
    bw.write_wheelfile(dist_info_dir)
    bw.write_record(temp_wheel_dir, dist_info_dir)

    package_name = "{dist}-{version}-{pyVer}-{abi}-{platform}".format(
        dist=pkg_name,
        version=pkg_version,
        pyVer='py27',
        abi='none',
        platform='any')
    base_name = os.path.join(os.path.dirname(dest), package_name)
    archive_wheelfile(base_name, temp_wheel_dir)

    cleanup(temp_deb_dir, temp_wheel_dir)

    res['rc'] = 0
    res['changed'] = True

    return res


def main():
    """Module entry point."""
    module = AnsibleModule(
        argument_spec=dict(
            src=dict(required=True),
            dest=dict(required=False)
        )
    )

    params = module.params
    src = params['src']
    dest = params['dest']
    if(not dest):
        dest = os.path.dirname(src)
    results = deb_to_wheel(module, src, dest)

    module.exit_json(**results)

# import module snippets
from ansible.module_utils.basic import * # noqa
if __name__ == '__main__':
    main()
