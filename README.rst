CouchApp: Standalone CouchDB Application Development Made Simple
================================================================
This is a forked version of the original python2-only CouchApp application provided in `couchapp <https://github.com/couchapp/couchapp>`_.
This repository is meant to provide a CouchApp application compatible with python3, for that, the following changes have been done:

* Removal of all Windows related code (it only supports Linux and MacOS now)
* Replacement of ``restkit`` by ``requests`` python library
* Removed all the codebase that is not required for ``couchapp push`` command.
* Tested in CouchDB 1.6.1 with plain http requests.

In short, this App can be used to construct and push your CouchDB application, based on a set of javascript/erlang scripts properly structured in a directory.


Installation
------------
**NOTE**: CMSCouchApp version 1.2.2 and 1.2.5 are broken and should not be used.

Couchapp requires Python3 (tested with Python 3.8).
Couchapp is most easily installed using the latest versions of the standard
python packaging tools, ``setuptools`` and ``pip``.
They may be installed like so::

    $ curl -O https://bootstrap.pypa.io/3.5/get-pip.py
    $ sudo python get-pip.py

Installing couchapp is then simply a matter of::

    $ pip install couchapp

or this way if you cannot access the root (or due to SIP on macOS),
then find the executable at ``~/.local/bin``.
For more info about ``--user``, please checkout ``pip help install``::

    $ pip install --user couchapp

To install/upgrade a development version of couchapp::

    $ pip install -e git+http://github.com/amaltaro/couchapp.git#egg=Couchapp

Note: Some installations need to use *sudo* command before each command
line.

Note: On debian system don't forget to install python-dev.
