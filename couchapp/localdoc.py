# -*- coding: utf-8 -*-
#
# This file is part of couchapp released under the Apache 2 license.
# See the NOTICE for more information.



import base64
import logging
import mimetypes
import os
import os.path
import re
import urllib.parse
from copy import copy
from itertools import chain

from couchapp import util
from couchapp.errors import ResourceNotFound
from couchapp.macros import package_shows, package_views

re_comment = re.compile("((?:\/\*(?:[^*]|(?:\*+[^*\/]))*\*+\/)|(?:\/\/.*))")

DEFAULT_IGNORE = """[
  // paths matching these regexps will not be pushed to the database
  // uncomment to activate; separate entries with ","
  // ".*~"
  // ".*\\\\.swp"
  // ".*\\\\.bak"
]"""

logger = logging.getLogger(__name__)


class LocalDoc(object):

    def __init__(self, path, create=False, docid=None, is_ddoc=True):
        self.docdir = path
        self.ignores = self._load_ignores()
        self.is_ddoc = is_ddoc
        self.docid = docid if docid else self.get_id()
        self._doc = {'_id': self.docid}

        if create:
            self.create()

    def _load_ignores(self):
        """
        load ignores from ``.couchappignore``

        The ``.couchappignore`` file is a json file containing a
        list of regexps for things to skip

        :return: a list of file name or ``[]`` for empty
        """
        path = os.path.join(self.docdir, '.couchappignore')
        if not os.path.exists(path):
            return []

        with open(path, 'r') as f:
            return util.json.loads(util.remove_comments(f.read()))

    def get_id(self):
        """
        if there is an ``_id`` file, docid is extracted from it,
        else we take the current folder name.
        """
        idfile = os.path.join(self.docdir, '_id')
        if os.path.exists(idfile):
            docid = util.read(idfile).split("\n")[0].strip()
            if docid:
                return docid

        dirname = os.path.split(self.docdir)[1]
        return '_design/%s' % dirname if self.is_ddoc else dirname

    def __repr__(self):
        return "<%s (%s/%s)>" % (self.__class__.__name__, self.docdir,
                                 self.docid)

    def __str__(self):
        return util.json.dumps(self.doc())

    def create(self):
        """
        Init a dir as a couchapp.

        Only create ``.couchapprc`` and ``.couchappignore``.
        Do nothing if ``.couchapprc`` exists.
        """
        util.setup_dir(self.docdir, require_empty=False)

        rcfile = os.path.join(self.docdir, '.couchapprc')
        ignfile = os.path.join(self.docdir, '.couchappignore')

        if not os.path.isfile(rcfile):
            util.write_json(rcfile, {})
            util.write(ignfile, DEFAULT_IGNORE)
        else:
            logger.info("CouchApp already initialized in %s.", self.docdir)

    def push(self, dbs, noatomic=False, browser=False, force=False,
             noindex=False):
        """
        Push a doc to a list of database ``dbs``.

        :param noatomic: If true, each attachments will be sent one by one.
        :param browser: If true, open browser after pushed.
        """
        for db in dbs:
            if noatomic:
                doc = self.doc(db, with_attachments=False, force=force)
                db.save_doc(doc, force_update=True)

                attachments = doc.get('_attachments') or {}

                for name, filepath in self.attachments():
                    if name not in attachments:
                        logger.debug("attach %s ", name)
                        db.put_attachment(doc, open(filepath, "r"),
                                          name=name)
            else:
                doc = self.doc(db, force=force)
                db.save_doc(doc, force_update=True)
            indexurl = self.index(db.raw_uri, doc['couchapp'].get('index'))
            if indexurl and not noindex:
                if "@" in indexurl:
                    u = urllib.parse.urlparse(indexurl)
                    indexurl = urllib.parse.urlunparse((u.scheme,
                                                    u.netloc.split("@")[-1],
                                                    u.path, u.params, u.query,
                                                    u.fragment))

                logger.info("Visit your CouchApp here:\n%s", indexurl)

    def attachment_stub(self, name, filepath):
        """
        Encode a byte-like object (attachment) using Base64, but return
        it in a text string format instead of bytes
        """
        re_sp = re.compile('\s')
        # Alan: strings are tough to deal in python3...
        # read a binary file and encode its bytes in base64
        content = util.read(filepath, utf8=False)
        b64content = base64.b64encode(util.to_bytestring(content))
        # then decode back to a string sequence
        att = {"data": re_sp.sub('', b64content.decode("utf-8")),
               "content_type": ';'.join([_f for _f in mimetypes.guess_type(name) if _f])}
        return att

    def doc(self, db=None, with_attachments=True, force=False):
        """
        Function to retrieve document object from document directory.

        :param with_attachments: If ``True``,
            attachments will be included and encoded
        """
        manifest = []
        objects = {}
        signatures = {}
        attachments = {}

        self._doc = {'_id': self.docid}

        # get designdoc
        self._doc.update(self.dir_to_fields(self.docdir, manifest=manifest))

        if 'couchapp' not in self._doc:
            self._doc['couchapp'] = {}

        self.olddoc = {}
        if db is not None:
            try:
                self.olddoc = db.open_doc(self._doc['_id'])
                attachments = self.olddoc.get('_attachments') or {}
                self._doc.update({'_rev': self.olddoc['_rev']})
            except ResourceNotFound:
                self.olddoc = {}

        if 'couchapp' in self.olddoc:
            old_signatures = self.olddoc['couchapp'].get('signatures', {})
        else:
            old_signatures = {}

        for name, filepath in self.attachments():
            signatures[name] = util.sign(filepath)
            if with_attachments and not old_signatures:
                logger.debug("attach %s ", name)
                attachments[name] = self.attachment_stub(name, filepath)

        if old_signatures:
            for name, signature in list(old_signatures.items()):
                cursign = signatures.get(name)
                if not cursign:
                    logger.debug("detach %s ", name)
                    del attachments[name]
                elif cursign != signature:
                    logger.debug("detach %s ", name)
                    del attachments[name]
                else:
                    continue

            if with_attachments:
                for name, filepath in self.attachments():
                    if old_signatures.get(name) != \
                            signatures.get(name) or force:
                        logger.debug("attach %s ", name)
                        attachments[name] = self.attachment_stub(name,
                                                                 filepath)

        self._doc['_attachments'] = attachments

        self._doc['couchapp'].update({
            'manifest': manifest,
            'objects': objects,
            'signatures': signatures
        })

        if self.docid.startswith('_design/'):  # process macros
            for funs in ['shows', 'lists', 'updates', 'filters', 'spatial']:
                if funs in self._doc:
                    package_shows(self._doc, self._doc[funs], self.docdir,
                                  objects)

            if 'validate_doc_update' in self._doc:
                tmp_dict = {'validate_doc_update':
                                self._doc["validate_doc_update"]}
                package_shows(self._doc, tmp_dict, self.docdir, objects)
                self._doc.update(tmp_dict)

            if 'views' in self._doc:
                # clean views
                # we remove empty views and malformed from the list
                # of pushed views. We also clean manifest
                views = {}
                dmanifest = {}
                for i, fname in enumerate(manifest):
                    if fname.startswith("views/") and fname != "views/":
                        name, ext = os.path.splitext(fname)
                        if name.endswith('/'):
                            name = name[:-1]
                        dmanifest[name] = i

                for vname, value in self._doc['views'].items():
                    if value and isinstance(value, dict):
                        views[vname] = value
                    else:
                        del manifest[dmanifest["views/%s" % vname]]
                self._doc['views'] = views
                package_views(self._doc, self._doc["views"], self.docdir,
                              objects)

            if "fulltext" in self._doc:
                package_views(self._doc, self._doc["fulltext"], self.docdir,
                              objects)
        return self._doc

    def check_ignore(self, item):
        """
        :param item: the relative path which starts from ``self.docdir``

        Given a path and a ignore list,
        e.g. ``foo/bar/baz.json`` and ``['bar']``,
        we will check
            * ``foo/bar/baz.json`` vs ``bar`` -> False
            * ``bar/baz.json`` vs ``bar`` -> True, then return
            * ``baz.json`` vs ``bar`` -> not checked
        """
        item = os.path.normpath(item)

        for pattern in self.ignores:
            # ('/' + item) is for abs path, some duplicated generated but work
            paths = chain(self._combine_path(item),
                          self._combine_path('/' + item))
            matches = (re.match(pattern + '$', i) for i in paths)
            if any(matches):
                logger.debug("ignoring %s", item)
                return True
        return False

    @classmethod
    def _combine_path(cls, p):
        """
        >>> tuple(LocalDoc._combine_path('foo/bar/qaz'))
        ('foo', 'foo/bar', 'foo/bar/qaz', 'bar', 'bar/qaz', 'qaz')

        >>> tuple(LocalDoc._combine_path('/foo/bar/qaz'))
        ('/foo', '/foo/bar', '/foo/bar/qaz', 'bar', 'bar/qaz', 'qaz')
        """
        ls = util.split_path(p)
        while ls:
            for i in cls._combine_dir(copy(ls)):
                yield i
            ls.pop(0)

    @staticmethod
    def _combine_dir(ls):
        """
        >>> tuple(LocalDoc._combine_dir(['foo', 'bar', 'qaz']))
        ('foo', 'foo/bar', 'foo/bar/qaz')
        """
        ret = tuple()
        while ls:
            ret += (ls.pop(0),)
            yield '/'.join(ret)

    def dir_to_fields(self, current_dir=None, depth=0, manifest=None):
        """
        Process a directory and get all members

        :param manifest: ``list``. We will have side effect on this param.
        """
        fields = {}  # return value
        manifest = manifest if manifest is not None else []
        current_dir = current_dir if current_dir else self.docdir

        for name in os.listdir(current_dir):
            current_path = os.path.join(current_dir, name)
            rel_path = util.relpath(current_path, self.docdir)
            if name.startswith('.'):
                continue
            elif self.check_ignore(rel_path):
                continue
            elif depth == 0 and name.startswith('_'):
                # files starting with "_" are always "special"
                continue
            elif name == '_attachments':
                continue
            elif depth == 0 and (name in ('couchapp', 'couchapp.json')):
                # we are in app_meta
                if name == "couchapp":
                    manifest.append('%s/' % rel_path)
                    content = self.dir_to_fields(
                            current_path, depth=depth + 1, manifest=manifest)
                else:
                    manifest.append(rel_path)
                    content = util.read_json(current_path)

                fields, content = self._meta_to_fields(fields, content)

            elif os.path.isdir(current_path):
                manifest.append('%s/' % rel_path)
                fields[name] = self.dir_to_fields(
                        current_path, depth=depth + 1, manifest=manifest)

            else:  # handler for normal file
                logger.debug('push %s', rel_path)
                # remove extension
                _name, ext = os.path.splitext(name)
                if _name in fields:
                    logger.warning("%(name)s is already in properties. "
                                   "Can't add (%(fqn)s)",
                                   {'name': _name, 'fqn': rel_path})
                else:
                    manifest.append(rel_path)
                    fields[_name] = self._encode_content(name, current_path)

        return fields

    @staticmethod
    def _meta_to_fields(fields, content):
        """
        Convert ``couchapp/`` or ``couchapp.json`` to fields

        This is a private subroutine for ``dir_to_fields``

        :return: fields, content
        """
        if not isinstance(content, dict):
            content = {'meta': content}

        content = content.copy()
        fields = fields.copy()

        for f in ('signatures', 'manifest', 'objects', 'length'):
            if f in content:
                del content[f]

        if 'couchapp' in fields:
            fields['couchapp'].update(content)
        else:
            fields['couchapp'] = content

        return fields, content

    @staticmethod
    def _encode_content(name, path):
        """
        This is a private subroutine for ``dir_to_fields``
        """
        if name.endswith('.json'):
            try:
                return util.read_json(path, raise_on_error=True)
            except ValueError:
                logger.error("Json invalid in %s", path)
                return ''

        try:
            content = util.read(path)
        except UnicodeDecodeError:
            logger.warning("%s isn't encoded in utf8", path)
            content = util.read(path, utf8=False)

            try:
                content.encode('utf-8')
            except UnicodeError:
                logger.warning("plan B didn't work, %s is a binary", path)
                logger.warning("use plan C: encode to base64")
                content = ("base64-encoded;%s" % base64.b64encode(content))
        # Alan: make sure to remove newline at the end of the string, otherwise it
        # breaks the design documents
        return content.rstrip("\n")

    def _process_attachments(self, path, vendor=None):
        """
        Processing directory to yield attachments.
        """
        if not os.path.isdir(path):
            raise StopIteration()

        for root, dirs, files in os.walk(path):
            for dir_ in dirs:
                _relpath = util.relpath(os.path.join(root, dir_),
                                        self.docdir)
                if self.check_ignore(_relpath):
                    dirs.remove(dir_)

            if not files:
                continue

            for filename in files:
                filepath = os.path.join(root, filename)
                _relpath = util.relpath(filepath, self.docdir)
                if self.check_ignore(_relpath):
                    continue

                name = util.relpath(filepath, path)
                if vendor is not None:
                    name = os.path.join('vendor', vendor, name)
                yield (name, filepath)

    def attachments(self):
        """
        This function yield a tuple (name, filepath) corresponding
        to each attachment (vendor, included) in the couchapp.
        ``name`` is the name of attachment in ``_attachments`` member
        and ``filepath`` the path to the attachment on the disk.

        attachments are processed later to allow us to send attachments inline
        or one by one.
        """
        # process main attachments
        dir_ = os.path.join(self.docdir, "_attachments")
        if os.path.isdir(dir_):
            for attachment in self._process_attachments(dir_):
                yield attachment

        vendordir = os.path.join(self.docdir, 'vendor')
        if not os.path.isdir(vendordir):
            logger.debug("%s don't exist", vendordir)
            return

        for name in os.listdir(vendordir):
            current_path = os.path.join(vendordir, name)
            if os.path.isdir(current_path):
                attachdir = os.path.join(current_path, '_attachments')
                if os.path.isdir(attachdir):
                    for attachment in self._process_attachments(attachdir, vendor=name):
                        yield attachment

    def index(self, dburl, index):
        if index is not None:
            return "%s/%s/%s" % (dburl, self.docid, index)
        elif os.path.isfile(os.path.join(self.docdir, "_attachments",
                                         'index.html')):
            return "%s/%s/index.html" % (dburl, self.docid)
        return False

    def to_json(self):
        return self.__str__()


def document(path, create=False, docid=None, is_ddoc=True):
    return LocalDoc(os.path.realpath(path), create=create, docid=docid,
                    is_ddoc=is_ddoc)
