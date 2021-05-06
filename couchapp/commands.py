# -*- coding: utf-8 -*-
#
# This file is part of couchapp released under the Apache 2 license.
# See the NOTICE for more information.

from __future__ import print_function

import logging
import os
import sys
import urllib

from couchapp import util
from couchapp.config import Config
from couchapp.errors import ResourceNotFound, AppError, BulkSaveError
from couchapp.localdoc import document

logger = logging.getLogger(__name__)


def hook(conf, path, hook_type, *args, **kwargs):
    if hook_type in conf.hooks:
        for h in conf.hooks.get(hook_type):
            if hasattr(h, 'hook'):
                h.hook(path, hook_type, *args, **kwargs)


def push(conf, path, *args, **opts):
    export = opts.get('export', False)
    noatomic = opts.get('no_atomic', False)
    browse = opts.get('browse', False)
    force = opts.get('force', False)
    dest = None
    doc_path = None
    if len(args) < 2:
        if export:
            if path is None and args:
                doc_path = args[0]
            else:
                doc_path = path
        else:
            doc_path = path
            if args:
                dest = args[0]
    else:
        doc_path = os.path.normpath(os.path.join(os.getcwd(), args[0]))
        dest = args[1]
    if doc_path is None:
        raise AppError("You aren't in a couchapp.")

    conf.update(doc_path)
    print("DEBUG doc_path: {}".format(doc_path))
    print("DEBUG dest: {}".format(dest))
    doc = document(doc_path, create=False, docid=opts.get('docid'))
    print("DEBUG doc: {}".format(doc))

    if export:
        if opts.get('output'):
            util.write_json(opts.get('output'), doc)
        else:
            print(doc.to_json())
        return 0

    dbs = conf.get_dbs(dest)

    hook(conf, doc_path, "pre-push", dbs=dbs)
    doc.push(dbs, noatomic, browse, force)
    hook(conf, doc_path, "post-push", dbs=dbs)

    docspath = os.path.join(doc_path, '_docs')
    if os.path.exists(docspath):
        pushdocs(conf, docspath, dest, *args, **opts)
    return 0


def pushdocs(conf, source, dest, *args, **opts):
    export = opts.get('export', False)
    noatomic = opts.get('no_atomic', False)
    browse = opts.get('browse', False)
    dbs = conf.get_dbs(dest)
    docs = []
    for d in os.listdir(source):
        docdir = os.path.join(source, d)
        if d.startswith('.'):
            continue
        elif os.path.isfile(docdir):
            if d.endswith(".json"):
                doc = util.read_json(docdir)
                docid, ext = os.path.splitext(d)
                doc.setdefault('_id', docid)
                doc.setdefault('couchapp', {})
                if export or not noatomic:
                    docs.append(doc)
                else:
                    for db in dbs:
                        db.save_doc(doc, force_update=True)
        else:
            doc = document(docdir, is_ddoc=False)
            if export or not noatomic:
                docs.append(doc)
            else:
                doc.push(dbs, True, browse)
    if docs:
        if export:
            docs1 = []
            for doc in docs:
                if hasattr(doc, 'doc'):
                    docs1.append(doc.doc())
                else:
                    docs1.append(doc)
            jsonobj = {'docs': docs}
            if opts.get('output'):
                util.write_json(opts.get('output'), jsonobj)
            else:
                print(util.json.dumps(jsonobj))
        else:
            for db in dbs:
                docs1 = []
                for doc in docs:
                    if hasattr(doc, 'doc'):
                        docs1.append(doc.doc(db))
                    else:
                        newdoc = doc.copy()
                        try:
                            rev = db.last_rev(doc['_id'])
                            newdoc.update({'_rev': rev})
                        except ResourceNotFound:
                            pass
                        docs1.append(newdoc)
                try:
                    db.save_docs(docs1)
                except BulkSaveError, e:
                    # resolve conflicts
                    docs1 = []
                    for doc in e.errors:
                        try:
                            doc['_rev'] = db.last_rev(doc['_id'])
                            docs1.append(doc)
                        except ResourceNotFound:
                            pass
                if docs1:
                    db.save_docs(docs1)
    return 0


if __name__ == "__main__":
    couchUrl = "http://USER:PASS@localhost:5984"
    couchDBName = "wmagent_summary"
    couchAppName = "WMStatsAgent"
    basePath = "/Users/amaltaro/Pycharm/WMCore/src/couchapps/"
    print("Installing %s into %s" % (couchAppName, urllib.unquote_plus(couchDBName)))

    couchappConfig = Config()
    print("AMR couchappConfig: {}".format(couchappConfig))
    print("AMR new basePath: {}".format(basePath))

    push(couchappConfig, "%s/%s" % (basePath, couchAppName),
         "%s/%s" % (couchUrl, couchDBName))
    print("Done")
    sys.exit(0)
