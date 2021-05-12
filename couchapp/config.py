# -*- coding: utf-8 -*-
#
# This file is part of couchapp released under the Apache 2 license.
# See the NOTICE for more information.

import logging
import os
import re
from copy import deepcopy

from couchapp import util
from couchapp.client import Database
from couchapp.errors import AppError

logger = logging.getLogger(__name__)


class Config(object):
    """ main object to read configuration from ~/.couchapp.conf or
    .couchapprc/couchapp.json in the couchapp folder.
    """
    DEFAULT_SERVER_URI = "http://127.0.0.1:5984"

    DEFAULTS = dict(
            env={},
            extensions=[],
            hooks={},
            vendors=[]
    )

    def __init__(self):
        self.rc_path = util.rcpath()
        self.global_conf = self.load(self.rc_path, self.DEFAULTS)
        self.local_conf = {}
        self.app_dir = util.findcouchapp(os.getcwd())
        if self.app_dir:
            self.local_conf = self.load_local(self.app_dir)

        self.conf = self.global_conf.copy()
        self.conf.update(self.local_conf)

    def load(self, path, default=None):
        """
        load config

        :type path: str or iterable
        """
        conf = deepcopy(default) if default is not None else {}
        paths = [path] if isinstance(path, str) else path

        for p in paths:
            if not os.path.isfile(p):
                continue
            try:
                new_conf = util.read_json(p, use_environment=True,
                                          raise_on_error=True)
            except ValueError:
                raise AppError("Error while reading '{0}'".format(p))
            conf.update(new_conf)

        return conf

    def load_local(self, app_path):
        """
        Load local config from app/couchapp.json and app/.couchapprc.
        If both of them contain same vars, the latter one will win.

        To prevent user from placing private data like db credentials,
        we will ignore ``env`` parts in ``couchapp.json``.
        """
        if not app_path:
            raise AppError("You aren't in a couchapp.")

        json_conf = self.load(os.path.join(app_path, 'couchapp.json'))
        # prevent user from place privating data in couchapp.json
        if 'env' in json_conf:
            logger.warning('Ignore `env` field in couchapp.json. '
                           'Please place your db credentials in .couchapprc.')
            del json_conf['env']

        return self.load(
                os.path.join(app_path, '.couchapprc'),
                default=json_conf)

    def update(self, path):
        """
        Given a couchapp path, and load the configs from it.
        """
        self.conf = self.global_conf.copy()
        self.local_conf.update(self.load_local(path))
        self.conf.update(self.local_conf)

    def get(self, key, default=None):
        try:
            return getattr(self, key)
        except AttributeError:
            pass
        return self.conf.get(key, default)

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            pass
        return self.conf[key]

    def __getattr__(self, key):
        try:
            getattr(super(Config, self), key)
        except AttributeError:
            if key in self.conf:
                return self.conf[key]
            raise

    def __contains__(self, key):
        return (key in self.conf)

    def __iter__(self):
        """
        We will get the key-value pair from the dict: self.conf
        """
        for k, v in list(self.conf.items()):
            yield (k, v)

    @property
    def extensions(self):
        """
        load extensions from conf

        :return: list of extension modules
        """
        return [util.load_py(uri, self)
                for uri in self.conf.get('extensions', tuple())]

    @property
    def hooks(self):
        return dict(
                (hooktype, [util.hook_uri(uri, self) for uri in uris])
                for hooktype, uris in list(self.conf.get('hooks', {}).items())
        )

    # TODO: add oauth management
    def get_dbs(self, db_string=None):
        """
        :type db_string: str
        """
        db_string = db_string or ''
        env = self.conf.get('env', {})
        is_full_uri = any(map(db_string.startswith,
                              ('http://', 'https://')))

        if not db_string and 'default' not in env:
            raise AppError("database isn't specified")
        elif not db_string and 'default' in env:
            dburls = env['default']['db']
        elif is_full_uri:
            dburls = db_string
        elif not is_full_uri:
            conf_uri = env.get(db_string, {}).get('db')
            default_uri = '{0}/{1}'.format(self.DEFAULT_SERVER_URI, db_string)

            dburls = conf_uri if conf_uri else default_uri

            del conf_uri, default_uri

        if isinstance(dburls, str):
            dburls = [dburls]

        use_proxy = any(k in os.environ for k in ('http_proxy', 'https_proxy'))

        return [Database(dburl, use_proxy=use_proxy) for dburl in dburls]

    def get_app_name(self, dbstring=None, default=None):
        dbstring = dbstring or ''
        env = self.conf.get('env', {})
        is_full_uri = re.match('(https?)://', dbstring)

        if not is_full_uri and dbstring in env:
            return env[dbstring].get('name', default)
        elif not is_full_uri and 'default' in env:
            return env['default'].get('name', default)
        return default
