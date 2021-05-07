# -*- coding: utf-8 -*-
#
# This file is part of couchapp released under the Apache 2 license.
# See the NOTICE for more information.

from __future__ import print_function

import logging
import os

from couchapp import util
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


def version(conf, *args, **opts):
    from couchapp import __version__
    print("Couchapp (version {0})".format(__version__))
    if opts.get('help', False):
        usage(conf, *args, **opts)
    return 0

def usage(conf, *args, **opts):
    if opts.get('version', False):
        version(conf, *args, **opts)
    print('Usage: couchapp [OPTIONS] [CMD] [CMDOPTIONS] [ARGS,...]')

    print()
    print('Options:')
    mainopts = []
    max_opt_len = len(max(globalopts, key=len))
    for opt in globalopts:
        print('\t{opt: <{max_len}}'.format(opt=get_switch_str(opt),
                                           max_len=max_opt_len))
        mainopts.append(opt[0])

    print()
    print('Commands:')
    commands = sorted(table.keys())
    max_len = len(max(commands, key=len))
    for cmd in commands:
        opts = table[cmd]
        print('\t{cmd: <{max_len}} {opts}'.format(
              cmd=cmd, max_len=max_len, opts=opts[2]))
        # Print each command's option list
        cmd_options = opts[1]
        if cmd_options:
            max_opt = max(cmd_options, key=lambda o: len(get_switch_str(o)))
            max_opt_len = len(get_switch_str(max_opt))
            for opt in cmd_options:
                print('\t\t{opt_str: <{max_len}} {opts}'.format(
                      opt_str=get_switch_str(opt), max_len=max_opt_len,
                      opts=opt[3]))
    return 0


def get_switch_str(opt):
    """
    Output just the '-r, --rev [VAL]' part of the option string.
    """
    if opt[2] is None or opt[2] is True or opt[2] is False:
        default = ""
    else:
        default = "[VAL]"
    if opt[0]:
        # has a short and long option
        return '-{opt[0]}, --{opt[1]} {default}'.format(opt=opt,
                                                        default=default)
    else:
        # only has a long option
        return '--{opt[1]} {default}'.format(opt=opt, default=default)


globalopts = [
    ('d', 'debug', None, "debug mode"),
    ('h', 'help', None, "display help and exit"),
    ('', 'version', None, "display version and exit"),
    ('v', 'verbose', None, "enable additionnal output"),
    ('q', 'quiet', None, "don't print any message")
]

pushopts = [
    ('', 'no-atomic', False, "send attachments one by one"),
    ('', 'export', False, "don't do push, just export doc to stdout"),
    ('', 'output', '', "if export is selected, output to the file"),
    ('b', 'browse', False, "open the couchapp in the browser"),
    ('', 'force', False, "force attachments sending")
]

table = {
    "push": (
        push,
        pushopts + [('', 'docid', '', "set docid")],
        "[OPTION]... [COUCHAPPDIR] DEST"
    ),
    "pushdocs": (
        pushdocs,
        pushopts,
        "[OPTION]... SOURCE DEST"
    ),
    "help": (usage, [], ""),
    "version": (version, [], "")
}
