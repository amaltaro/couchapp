# -*- coding: utf-8 -*-
#
# This file is part of couchapp released under the Apache 2 license.
# See the NOTICE for more information.

import string
import codecs
import inspect
import json
import logging
import os
import re
import subprocess
from hashlib import md5
from importlib import import_module, util
from urllib.parse import urlparse, urlunparse

from couchapp.errors import AppError, ScriptError

logger = logging.getLogger(__name__)

def user_rcpath():
    return [os.path.expanduser('~/.couchapp.conf')]

def user_path():
    return [os.path.expanduser('~/.couchapp')]


relpath = os.path.relpath
#TODO: manage system configuration file
_rcpath = None


def rcpath():
    """
    Get global configuration.

    This function will take the environment var, ``COUCHAPPCONF_PATH``,
    as the search path list.
    """
    global _rcpath
    if _rcpath is not None:
        return _rcpath

    conf_path = os.environ.get('COUCHAPPCONF_PATH')
    if conf_path is None:
        _rcpath = user_rcpath()
        return _rcpath

    _rcpath = []
    for p in conf_path.split(os.pathsep):
        if not p:
            continue
        if not os.path.isdir(p):
            _rcpath.append(p)
            continue
        _rcpath.extend(os.path.join(p, f) for f in os.listdir(p)
                       if f == 'couchapp.conf')
    return _rcpath


def findcouchapp(p):
    """
    Find couchapp top level dir from sub dir
    """
    while not os.path.isfile(os.path.join(p, ".couchapprc")):
        oldp, p = p, os.path.dirname(p)
        if p == oldp:
            return None
    return p


def discover_apps(path):
    """
    Given a path as parent dir, depth=1, return a list of the couchapps.
    It will ignore all hidden dir.

    :type path: str
    """
    apps = []

    for item in os.listdir(path):
        full_path = os.path.join(path, item)
        if item.startswith('.'):  # skip hidden file
            continue
        elif os.path.isdir(full_path) and iscouchapp(full_path):
            apps.append(full_path)

    return apps


def iscouchapp(path):
    """
    A couchapp MUSH have ``.couchapprc``

    :type path: str
    :return: bool
    """
    return os.path.isfile(os.path.join(path, '.couchapprc'))


def in_couchapp():
    """ return path of couchapp if we are somewhere in a couchapp. """
    current_path = os.getcwd()
    parent = ''
    while 1:
        current_rcpath = os.path.join(current_path, '.couchapprc')
        if os.path.exists(current_rcpath):
            if current_rcpath in rcpath():
                return False
            return current_path
        parent = os.path.normpath(os.path.join(current_path, '../'))
        if parent == current_path:
            return False
        current_path = parent


def get_appname(docid):
    """ get applicaton name for design name"""
    return docid.split('_design/')[1]


def to_bytestring(s):
    """ convert to bytestring an unicode """
    if isinstance(s, str):
        return s.encode('utf-8')
    else:
        return s


# function borrowed to Fusil project(http://fusil.hachoir.org/)
# which allowed us to use it under Apache 2 license.
def locate_program(program, use_none=False, raise_error=False):
    if os.path.isabs(program):
        # Absolute path: nothing to do
        return program
    if os.path.dirname(program):
        # ./test => $PWD/./test
        # ../python => $PWD/../python
        program = os.path.normpath(os.path.realpath(program))
        return program
    if use_none:
        default = None
    else:
        default = program
    paths = os.getenv('PATH')
    if not paths:
        if raise_error:
            raise ValueError("Unable to get PATH environment variable")
        return default
    for path in paths.split(os.pathsep):
        filename = os.path.join(path, program)
        if os.access(filename, os.X_OK):
            return filename
    if raise_error:
        raise ValueError("Unable to locate program %r in PATH" % program)
    return default


def deltree(path):
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            os.unlink(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    try:
        os.rmdir(path)
    except:
        pass


def split_path(path):
    parts = []
    while True:
        head, tail = os.path.split(path)
        parts = [tail] + parts
        path = head
        if not path:
            break
        elif path == os.path.realpath('/'):
            parts[0] = os.path.join(os.path.realpath('/'), parts[0])
            break
    return parts


def sign(fpath):
    """ return md5 hash from file content

    :attr fpath: string, path of file

    :return: string, md5 hexdigest
    """
    if os.path.isfile(fpath):
        m = md5()
        with open(fpath, 'rb') as fp:
            try:
                while 1:
                    data = fp.read(8096)
                    if not data:
                        break
                    m.update(data)
            except IOError as msg:
                logger.error('%s: I/O error: %s\n', fpath, msg)
                return 1
            return m.hexdigest()
    return ''


def read(fname, utf8=True, force_read=False):
    """ read file content"""
    if utf8:
        try:
            with codecs.open(fname, 'rb', "utf-8") as f:
                return f.read()
        except UnicodeError:
            if force_read:
                return read(fname, utf8=False)
            raise
    else:
        with open(fname, 'rb') as f:
            return f.read()


def write(fname, content):
    """ write content in a file

    :type fname: string, filename
    :type content: str
    """
    with open(fname, 'wb') as f:
        f.write(to_bytestring(content))
        f.write('\n')


def write_json(fname, obj):
    """
    serialize obj in json and save it

    :type fname: str
    :param obj: serializable builtin type,
        or any obj has ``to_json`` method
    """
    try:
        val = json.dumps(obj).encode('utf-8')
    except TypeError:
        val = obj.to_json()
    write(fname, val)


def read_json(fname, use_environment=False, raise_on_error=False):
    """ read a json file and deserialize

    :attr filename: string
    :attr use_environment: boolean, default is False. If
    True, replace environment variable by their value in file
    content

    :return: dict or list
    """
    try:
        data = read(fname, force_read=True)
    except IOError as e:
        if e.args[0] == 2:
            return {}
        raise

    if use_environment:
        data = string.Template(data).substitute(os.environ)

    try:
        data = json.loads(data)
    except ValueError:
        logger.error("Json is invalid, can't load %s", fname)
        if not raise_on_error:
            return {}
        raise
    return data


_vendor_dir = None


def vendor_dir():
    global _vendor_dir
    if _vendor_dir is None:
        _vendor_dir = os.path.join(os.path.dirname(__file__), 'vendor')
    return _vendor_dir


def expandpath(path):
    return os.path.expanduser(os.path.expandvars(path))


def load_py(uri, cfg):
    # while porting to python3, I found this snippet for loading a python module
    # https://github.com/epfl-scitas/spack/blob/af6a3556c4c861148b8e1adc2637685932f4b08a/lib/spack/llnl/util/lang.py#L595-L622
    if os.path.exists(uri):
        name, ext = os.path.splitext(os.path.basename(uri))
        spec = util.spec_from_file_location(name, uri)
        script = util.module_from_spec(spec)
        spec.loader.exec_module(script)
    else:
        if ":" in uri:
            parts = uri.rsplit(":", 1)
            name, objname = parts[0], parts[1]
            mod = import_module(name)

            script_class = getattr(mod, objname)
            try:
                if inspect.getargspec(script_class.__init__) > 1:
                    script = script_class(cfg)
                else:
                    script = script_class()
            except TypeError:
                script = script_class()
        else:
            script = import_module(uri)
    script.__dict__['__couchapp_cfg__'] = cfg
    return script


class ShellScript(object):
    """ simple object used to manage extensions or hooks from external
    scripts in any languages """

    def __init__(self, cmd):
        self.cmd = cmd

    def hook(self, *args, **options):
        cmd = self.cmd + " "

        child_stdout, child_stderr = sh_open(cmd)
        if child_stderr:
            raise ScriptError(str(child_stderr))
        return child_stdout


def hook_uri(uri, cfg):
    if isinstance(uri, list):
        (script_type, script_uri) = uri
        if script_type == "py":
            return load_py(script_uri, cfg)
    else:
        script_uri = uri
    return ShellScript(script_uri)


RE_COMMENT = re.compile(
    r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"'
    , re.DOTALL | re.MULTILINE)


def remove_comments(text):
    """
    remove comments string in json text

    :param str text: the json text
    """
    def replace(m):
        """
        :param m: the regex match object
        """
        s = m.group(0)
        if s.startswith('/'):
            return ''
        return s
    return re.sub(RE_COMMENT, replace, text)


def sh_open(cmd, bufsize=0):
    """
    run shell command with :mod:`subprocess`

    :param str cmd: the command string
    :param int bufsize: the bufsize passed to ``subprocess.Popen``
    :return:  a tuple contains (stdout, stderr)
    """
    closefds = (os.name == 'posix')

    p = subprocess.Popen(cmd, shell=True, bufsize=bufsize,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, close_fds=closefds)
    # use ``communicate`` to avoid PIPE deadlock
    out, err = p.communicate()

    return (out, err)


def is_empty_dir(path):
    if not os.listdir(path):
        return True
    return False


def setup_dir(path, require_empty=True):
    """
    If dir exists, check it empty or not.
    If dir does not exist, make one.
    """
    isdir = os.path.isdir(path)

    if isdir and not require_empty:
        return
    elif isdir and require_empty and is_empty_dir(path):
        return
    elif isdir and require_empty and not is_empty_dir(path):
        raise AppError("dir '{0}' is not empty".format(path))
    elif os.path.exists(path) and not isdir:
        raise AppError("'{0}': File exists".format(path))

    os.mkdir(path)


def setup_dirs(path_list, *args, **kwargs):
    """
    setup a list of dirs.

    :param path_list: iterable

    Other arguments please refer to ``setup_dir``.
    """
    for p in path_list:
        setup_dir(p, *args, **kwargs)


def sanitizeURL(url):
    """
    Take the url with/without username and password and return sanitized url,
    username and password in dict format
    WANNING: Don't use ':' in username or password.
    """
    endpoint_components = urlparse(url)
    # Cleanly pull out the user/password from the url
    if endpoint_components.port:
        netloc = '%s:%s' % (endpoint_components.hostname,
                            endpoint_components.port)
    else:
        netloc = endpoint_components.hostname

    # Build a URL without the username/password information
    url = urlunparse(
        [endpoint_components.scheme,
         netloc,
         endpoint_components.path,
         endpoint_components.params,
         endpoint_components.query,
         endpoint_components.fragment])

    return {'url': url, 'username': endpoint_components.username,
            'password': endpoint_components.password}