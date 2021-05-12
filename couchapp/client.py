# -*- coding: utf-8 -*-
#
# This file is part of couchapp released under the Apache 2 license.
# See the NOTICE for more information.


import base64
import itertools
import json
import logging
import re

import requests

from urllib.parse import quote
from couchapp import __version__
from couchapp.errors import ResourceNotFound, ResourceConflict, \
    PreconditionFailed, RequestFailed, BulkSaveError, Unauthorized, \
    InvalidAttachment

USER_AGENT = "couchapp/{0}".format(__version__)

aliases = {
    'id': '_id',
    'rev': '_rev'
}

UNKNOWN_VERSION = tuple()

logger = logging.getLogger(__name__)


class CouchdbResponse(requests.Response):

    def __init__(self, respObj):
        super(CouchdbResponse, self).__init__()
        self.response = respObj

    @property
    def json_body(self):
        """
        Parse the response object and return its json data,
        or raise an exception if it failed
        """
        if self.response.ok:
            logger.debug("Response status_code: %s", self.response.status_code)
            logger.debug("Response text: %s", self.response.text)
            logger.debug("Response headers: %s", self.response.headers)
            logger.debug("Response encoding: %s", self.response.encoding)
            logger.debug("Response content: %s", self.response.content)
            self.response.close()
            try:
                return self.response.json()
            except ValueError:
                # No JSON object could be decoded
                return self.response.content
        else:
            errorReason = self.response.reason
            errorCode = self.response.status_code

        if errorCode in (401, 403):
            raise Unauthorized(str(self.response))
        elif errorCode == 404:
            raise ResourceNotFound(errorReason, http_code=errorCode, response=self.response.text)
        elif errorCode == 409:
            raise ResourceConflict(errorReason, http_code=errorCode, response=self.response.text)
        elif errorCode == 412:
            raise PreconditionFailed(errorReason, http_code=errorCode, response=self.response.text)
        else:
            raise RequestFailed(str(self.response))


class CouchdbResource(object):

    def __init__(self, uri="http://127.0.0.1:5984", **client_opts):
        """Constructor for a `CouchdbResource` object.

        CouchdbResource represent an HTTP resource to CouchDB.

        @param uri: str, full uri to the server.
        """
        self.uri = uri
        # FIXME: dangerous if the database name is not part of the URI
        # self.database = uri.rsplit("/", 1)[1]
        self.client_opts = client_opts
        # requests.__init__(self, uri=uri, **client_opts)
        self.safe = ":/%"

    def copy(self, path=None, headers=None, **params):
        """ add copy to HTTP verbs """
        return self.request('COPY', path=path, headers=headers, **params)

    def request(self, method, path=None, payload=None, headers=None,
                params_dict=None, **params):
        """ Perform HTTP call to the couchdb server and manage
        JSON conversions, support GET, POST, PUT and DELETE.

        Usage example, get infos of a couchdb server on
        http://127.0.0.1:5984 :


            import couchdbkit.CouchdbResource
            resource = couchdbkit.CouchdbResource()
            infos = resource.request('GET')

        @param method: str, the HTTP action to be performed:
            'GET', 'HEAD', 'POST', 'PUT', or 'DELETE'
        @param path: str or list, path to add to the uri
        @param data: str or string or any object that could be
            converted to JSON.
        @param headers: dict, optional headers that will
            be added to HTTP request.
        @param raw: boolean, response return a Response object
        @param params: Optional parameterss added to the request.
            Parameterss are for example the parameters for a view. See
            `CouchDB View API reference
            <http://wiki.apache.org/couchdb/HTTP_view_API>`_ for example.

        @return: tuple (data, resp), where resp is an `httplib2.Response`
            object and data a python object (often a dict).
        """
        if path:
            path = "{}/{}".format(self.uri, path)
        else:
            path = self.uri
        headers = headers or {}
        headers.setdefault('Accept', 'application/json')
        headers.setdefault('User-Agent', USER_AGENT)

        logger.debug("Request: %s %s", method, path)

        try:
            resp = requests.request(method, url=path, data=payload,
                                    headers=headers, **params)
        except Exception as e:
            logger.exception("Error making a CouchdbResource call. Details: %s", e)
            raise RequestFailed('unknown error [%s]', str(e))
        return CouchdbResponse(resp).json_body


def couchdb_version(server_uri):
    res = CouchdbResource(server_uri)

    try:
        resp = res.request("GET")
    except Exception:
        return UNKNOWN_VERSION

    version = CouchdbResponse(resp).json_body
    t = []
    for p in version.split("."):
        try:
            t.append(int(p))
        except ValueError:
            continue

    return tuple(t)


class Uuids(object):

    def __init__(self, uri, max_uuids=1000, **client_opts):
        api = "_uuids"
        uri = "{}/{}".format(uri, api)
        self.res = CouchdbResource(uri=uri, **client_opts)
        self._uuids = []
        self.max_uuids = max_uuids

    def __next__(self):
        if not self._uuids:
            self.fetch_uuids()
        self._uuids, res = self._uuids[:-1], self._uuids[-1]
        return res

    def __iter__(self):
        return self

    def fetch_uuids(self):
        count = self.max_uuids - len(self._uuids)
        resp = self.res.request("GET", count=count)
        self._uuids += resp.json_body['uuids']


class Database(object):
    """ Object that abstract access to a CouchDB database
    A Database object can act as a Dict object.
    """

    def __init__(self, uri, create=True, **client_opts):
        if uri.endswith("/"):
            uri = uri[:-1]

        self.raw_uri = uri
        self.res = CouchdbResource(uri=uri, **client_opts)
        self.server_uri, self.dbname = uri.rsplit('/', 1)

        self.uuids = Uuids(self.server_uri, **client_opts)

        if create:
            # create the db
            try:
                self.res.request("HEAD")
            except ResourceNotFound:
                self.res.request("PUT")

    def delete(self):
        self.res.request("DELETE")

    def info(self):
        """
        Get database information
        @return: dict
        """
        return self.res.request("GET")

    def all_docs(self, **params):
        """
        return all_docs
        """
        return self.view('_all_docs', **params)

    def open_doc(self, docid, wrapper=None, **params):
        """Open document from database

        Args:
        @param docid: str, document id to retrieve
        @param rev: if specified, allows you to retrieve
        a specific revision of document
        @param wrapper: callable. function that takes dict as a param.
        Used to wrap an object.
        @params params: Other params to pass to the uri (or headers)

        @return: dict, representation of CouchDB document as
         a dict.
        """
        resp = self.res.request("GET", escape_docid(docid), **params)

        if wrapper is not None:
            if not callable(wrapper):
                raise TypeError("wrapper isn't a callable")
            return wrapper(resp)
        return resp

    def save_doc(self, doc, encode=False, force_update=False, **params):
        """ Save a document. It will use the `_id` member of the document
        or request a new uuid from CouchDB. IDs are attached to
        documents on the client side because POST has the curious property of
        being automatically retried by proxies in the event of network
        segmentation and lost responses.

        @param doc: dict.  doc is updated
        with doc '_id' and '_rev' properties returned
        by CouchDB server when you save.
        @param force_update: boolean, if there is conlict, try to update
        with latest revision
        @param encode: Encode attachments if needed (depends on couchdb
        version)

        @return: new doc with updated revision an id
        """
        if '_attachments' in doc and encode:
            doc['_attachments'] = encode_attachments(doc['_attachments'])

        headers = params.get('headers', {})
        headers.setdefault('Content-Type', 'application/json')
        params['headers'] = headers

        if '_id' in doc:
            docid = escape_docid(doc['_id'])
            try:
                resp = self.res.request("PUT", docid, payload=json.dumps(doc), **params)
            except ResourceConflict:
                if not force_update:
                    raise
                rev = self.last_rev(doc['_id'])
                doc['_rev'] = rev
                resp = self.res.request("PUT", docid, payload=json.dumps(doc), **params)
        else:
            json_doc = json.dumps(doc)
            try:
                doc['_id'] = next(self.uuids)
                resp = self.res.request("PUT", doc['_id'], payload=json_doc, **params)
            except ResourceConflict:
                resp = self.res.request("POST", payload=json_doc, **params)

        json_res = resp
        doc1 = {}
        for a, n in list(aliases.items()):
            if a in json_res:
                doc1[n] = json_res[a]
        doc.update(doc1)
        return doc

    def last_rev(self, docid):
        """ Get last revision from docid (the '_rev' member)
        @param docid: str, undecoded document id.

        @return rev: str, the last revision of document.
        """
        r = self.res.request("HEAD", escape_docid(docid))
        if "etag" in r.headers:
            # yeah new couchdb handle that
            return r.headers['etag'].strip('"')
        # old way ..
        doc = self.open_doc(docid)
        return doc['_rev']

    def delete_doc(self, id_or_doc):
        """ Delete a document
        @param id_or_doc: docid string or document dict

        """
        if isinstance(id_or_doc, (bytes, str)):
            resp = self.res.request("DELETE", escape_docid(id_or_doc),
                                    rev=self.last_rev(id_or_doc))
        else:
            docid = id_or_doc.get('_id')
            if not docid:
                raise ValueError('Not valid doc to delete (no doc id)')
            rev = id_or_doc.get('_rev', self.last_rev(docid))
            resp = self.res.request("DELETE", escape_docid(docid), rev=rev)
        return resp

    def save_docs(self, docs, all_or_nothing=False, use_uuids=True):
        """ Bulk save. Modify Multiple Documents With a Single Request

        @param docs: list of docs
        @param use_uuids: add _id in doc who don't have it already set.
        @param all_or_nothing: In the case of a power failure, when the
        database restarts either all the changes will have been saved or none
        of them. However, it does not do conflict checking, so the documents
        will.


        @return doc lists updated with new revision or raise BulkSaveError
        exception. You can access to doc created and docs in error as
        properties of this exception.
        """

        def is_id(doc):
            return '_id' in doc

        if use_uuids:
            noids = []
            for k, g in itertools.groupby(docs, is_id):
                if not k:
                    noids = list(g)

            for doc in noids:
                nextid = next(self.uuids)
                if nextid:
                    doc['_id'] = nextid

        payload = {"docs": docs}
        if all_or_nothing:
            payload["all-or-nothing"] = True

        # update docs
        res = self.res.request("POST", '/_bulk_docs', payload=json.dumps(payload),
                               headers={'Content-Type': 'application/json'})

        json_res = res
        errors = []
        for i, r in enumerate(json_res):
            if 'error' in r:
                doc1 = docs[i]
                doc1.update({'_id': r['id'],
                             '_rev': r['rev']})
                errors.append(doc1)
            else:
                docs[i].update({'_id': r['id'],
                                '_rev': r['rev']})

        if errors:
            raise BulkSaveError(docs, errors)

    def delete_docs(self, docs, all_or_nothing=False, use_uuids=True):
        """ multiple doc delete."""
        for doc in docs:
            doc['_deleted'] = True
        return self.save_docs(docs, all_or_nothing=all_or_nothing,
                              use_uuids=use_uuids)

    def fetch_attachment(self, id_or_doc, name, headers=None):
        """ get attachment in a document

        @param id_or_doc: str or dict, doc id or document dict
        @param name: name of attachment default: default result
        @param header: optionnal headers (like range)

        @return: `couchdbkit.resource.CouchDBResponse` object
        """
        if isinstance(id_or_doc, (str, bytes)):
            docid = id_or_doc
        else:
            docid = id_or_doc['_id']

        return self.res.request("GET", "%s/%s" % (escape_docid(docid), name),
                                headers=headers)

    def put_attachment(self, doc, content=None, name=None, headers=None):
        """ Add attachement to a document. All attachments are streamed.

        @param doc: dict, document object
        @param content: string, iterator,  fileobj
        @param name: name or attachment (file name).
        @param headers: optionnal headers like `Content-Length`
        or `Content-Type`

        @return: updated document object
        """
        headers = {}
        content = content or ""

        if name is None:
            if hasattr(content, "name"):
                name = content.name
            else:
                raise InvalidAttachment('You should provid a valid ' +
                                        'attachment name')
        name = quote(name, safe="")
        res = self.res.request("PUT", "%s/%s" % (escape_docid(doc['_id']), name),
                               payload=content, headers=headers, rev=doc['_rev'])
        json_res = res

        if 'ok' in json_res:
            return doc.update(self.open_doc(doc['_id']))
        return False

    def delete_attachment(self, doc, name):
        """ delete attachement to the document

        @param doc: dict, document object in python
        @param name: name of attachement

        @return: updated document object
        """
        name = quote(name, safe="")
        self.res.request("DELETE", "%s/%s" % (escape_docid(doc['_id']), name),
                         rev=doc['_rev'])
        return doc.update(self.open_doc(doc['_id']))

    def view(self, view_name, **params):
        try:
            dname, vname = view_name.split("/")
            path = "/_design/%s/_view/%s" % (dname, vname)
        except ValueError:
            path = view_name

        if "keys" in params:
            keys = params.pop("keys")
            return self.res.request("POST", path, json.dumps({"keys": keys}, **params))

        return self.res.request("GET", path, **params)


def encode_params(params):
    """ encode parameters in json if needed """
    _params = {}
    if params:
        for name, value in list(params.items()):
            if value is None:
                continue
            if name in ('key', 'startkey', 'endkey') \
                    or not isinstance(value, str):
                value = json.dumps(value).encode('utf-8')
            _params[name] = value
    return _params


def escape_docid(docid):
    if docid.startswith('/'):
        docid = docid[1:]
    if docid.startswith('_design'):
        docid = '_design/%s' % quote(docid[8:], safe='')
    else:
        docid = quote(docid, safe='')
    return docid


def encode_attachments(attachments):
    re_sp = re.compile('\s')
    for k, v in attachments.items():
        if v.get('stub', False):
            continue
        else:
            v['data'] = re_sp.sub('', base64.b64encode(v['data']))
    return attachments
