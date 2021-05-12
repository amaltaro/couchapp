# -*- coding: utf-8 -*-
#
# This file is part of couchapp released under the Apache 2 license.
# See the NOTICE for more information.



import argparse
import logging
import os
import sys

from couchapp import __version__
from couchapp import util
from couchapp.config import Config
from couchapp.errors import ResourceNotFound, BulkSaveError
from couchapp.localdoc import document

logger = logging.getLogger(__name__)


def hook(conf, path, hook_type, *args, **kwargs):
    if hook_type in conf.hooks:
        for h in conf.hooks.get(hook_type):
            if hasattr(h, 'hook'):
                h.hook(path, hook_type, *args, **kwargs)


def push(path_app, url_dest, opts=None):
    """
    This function will build the CouchDB application and push all
    the documents into CouchDB
    :param path_app: string with the absolute path to the CouchApp source code
    :param url_dest: string with the CouchDB URL and database name destination
    :param opts: an argparse.Namespace object in the following format:
        Namespace(export=False, force=False, no_atomic=False, output='blah', version=True)
    """
    browse = False  # FIXME: deprecated! It must be removed
    if opts:
        export = opts.export
        output_file = opts.output
        noatomic = opts.no_atomic
        force = opts.force
    else:
        export, output_file, noatomic, force = False, None, False, False

    app_name = path_app.rsplit("/", 1)[1]
    safe_url = util.sanitizeURL(url_dest)['url']
    print("Installing {} app into database: {}".format(app_name, safe_url))
    logger.debug("Application path: %s", path_app)
    logger.debug("CouchDB destination: %s", safe_url)
    couchapp_config = Config()
    couchapp_config.update(path_app)

    doc = document(path_app, create=False)

    if export:
        if output_file:
            util.write_json(output_file, doc)
        else:
            print(doc.to_json())
        return 0

    dbs = couchapp_config.get_dbs(url_dest)

    hook(couchapp_config, path_app, "pre-push", dbs=dbs)
    doc.push(dbs, noatomic, browse, force)
    hook(couchapp_config, path_app, "post-push", dbs=dbs)

    docspath = os.path.join(path_app, '_docs')
    if os.path.exists(docspath):
        pushdocs(couchapp_config, docspath, url_dest, export, noatomic, browse, output_file)
    return 0


def pushdocs(conf, source, dest, export, noatomic, browse, output_file):
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
            if output_file:
                util.write_json(output_file, jsonobj)
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
                except BulkSaveError as e:
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


def version():
    print("Couchapp (version {})\n".format(__version__))


def main():
    """
    Entry door taking the necessary parameters via command line
    """
    parser = argparse.ArgumentParser(prog='couchapp', description="CMSCouchApp Tool")
    parser.add_argument('push', default="push")
    parser.add_argument('-p', '--path_app', help='Absolute path to the couch app to be installed')
    parser.add_argument('-c', '--couch_uri', help='Target couch URI with the database name')
    parser.add_argument('-v', '--version', action="store_true", help='Display version and exit')
    # push options
    parser.add_argument('-n', '--no-atomic', action="store_true",
                        help='Send attachments one by one')
    parser.add_argument('-e', '--export', action="store_true",
                        help='Do not push, just export doc to stdout')
    parser.add_argument('-o', '--output', help='If --export is enabled, output to the file')
    parser.add_argument('-f', '--force', action="store_true",
                        help='Force attachments sending')
    args = parser.parse_args()
    if args.version:
        version()

    if not args.path_app and not args.couch_uri:
        print("ERROR: `path_app` and `couch_uri` parameters are mandatory")
        parser.print_help()
        sys.exit(1)

    # Now actually push the Apps
    push(args.path_app, args.couch_uri, args)
    sys.exit(0)


if __name__ == "__main__":
    main()
