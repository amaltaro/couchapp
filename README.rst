CouchApp: Standalone CouchDB Application Development Made Simple
================================================================
This is a forked version of the original python2-only CouchApp application provided in `couchapp <https://github.com/couchapp/couchapp>`_.
This repository is meant to provide a CouchApp application compatible with python3, for that, the following changes have been done:

* Removal of all Windows related code (it only supports Linux and MacOS now)
* Replacement of ``restkit`` by ``requests`` python library (its only third-party dependency!)
* Removed all the codebase that is not required for ``couchapp push`` command.
* Tested in CouchDB 1.6.1 with plain http requests.

In short, this App can be used to construct and push your CouchDB application, starting from a properly organized directory structure with javascript/erlang/html/css scripts and files.


Installation
------------
Couchapp requires Python2 (tested with Python 2.7) for versions in the ``1.2.x`` cycle.
Starting in ``1.3.x`` cycle, it will require Python3 (tested with Python 3.8).

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

Releases
--------
For **python2**, the recommended version is: ``1.2.10``.

For **Python3**, a new release will be made available very soon, starting with ``1.3.0``. Note that once it is released, python2 support will be dropped.

Last but not least, releases from ``1.2.2`` to ``1.2.7`` are not fully functional and should not be used.

Pushing your CouchApp
---------------------
Once you have installed the CMSCouchapp library, you can install your CouchDB application with a command like:

``couchapp push -p /data/TestCouchApp -c http://localhost:5984/test_database_name``


or if you want to simply visualize how the design document would look like, in a dry-run mode, you could run:

``couchapp push -p /data/TestCouchApp -c http://localhost:5984/test_database_name --export``

which would dump the design document into stdout.