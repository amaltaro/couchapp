# -*- coding: utf-8 -*-
#
# This file is part of couchapp released under the Apache 2 license.
# See the NOTICE for more information.

import os
import sys

from setuptools import setup, find_packages

import couchapp

if not hasattr(sys, 'version_info') or sys.version_info < (2, 7, 13, 'final'):
    raise SystemExit("Couchapp requires Python 2.6 or later.")


def get_data_files():
    data_files = [('couchapp',
                   ["LICENSE", "MANIFEST.in", "NOTICE", "README.rst", "THANKS"])]
    return data_files


def ordinarypath(p):
    return p and p[0] != '.' and p[-1] != '~'


def get_packages_data():
    packagedata = {'couchapp': []}
    return packagedata


CLASSIFIERS = ['License :: OSI Approved :: Apache Software License',
               'Intended Audience :: Developers',
               'Intended Audience :: System Administrators',
               'Development Status :: 4 - Beta',
               'Programming Language :: Python :: 2.7',
               'Operating System :: POSIX',
               'Topic :: Database',
               'Topic :: Utilities'
               ]


def main():
    # read long description
    with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as f:
        long_description = f.read()

    INSTALL_REQUIRES = ['requests==2.25.1']

    options = dict(
            name='CMSCouchapp',
            version=couchapp.__version__,
            url='http://github.com/amaltaro/couchapp',
            license='Apache License 2',
            author='Alan Malta',
            author_email='alan.malta@cern.ch',
            description='Standalone CouchDB Application Development Made Simple.',
            long_description=long_description,
            keywords='couchdb couchapp',
            platforms=['unix'],
            classifiers=CLASSIFIERS,
            packages=find_packages(),
            data_files=get_data_files(),
            include_package_data=True,
            zip_safe=False,
            install_requires=INSTALL_REQUIRES,
            entry_points={
                'console_scripts': [
                    'couchapp = couchapp.commands:usage'
                ],
            },
    )
    setup(**options)

    if __name__ == "__main__":
        main()
