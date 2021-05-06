# -*- coding: utf-8 -*-
#
# This file is part of couchapp released under the Apache 2 license.
# See the NOTICE for more information.

class CouchError(Exception):
    """Generic error thrown by CouchDB"""

    def __init__(self, reason, http_code=None, response=None):
        super(CouchError, self).__init__(self)
        self.reason = reason
        self.http_code = http_code
        self.response = response

    def __str__(self):
        "Stringify the error"
        return "CouchDB Error! Exit code: {}, Reason: {}, Response: {}".format(self.http_code,
                                                                               self.reason,
                                                                               self.response)


class AppError(Exception):
    """ raised when a application error appear """


class MacroError(Exception):
    """ raised for macro errors"""


class VendorError(Exception):
    """ vendor error """


class ScriptError(Exception):
    """ exception raised in external script"""


class PreconditionFailed(Exception):
    """ precondition failed error """


class ResourceNotFound(CouchError):
    """ raised when a resource not found on CouchDB"""


class ResourceConflict(CouchError):
    """ raised when a conflict occured"""


class RequestFailed(CouchError):
    """ raised when an http error occurs"""


class Unauthorized(CouchError):
    """ raised when not authorized to access to CouchDB"""


class CommandLineError(Exception):
    """ error when a bad command line is passed"""


class BulkSaveError(CouchError):
    """ error raised when therer are conflicts in bulk save"""

    def __init__(self, docs, errors):
        super(BulkSaveError, self).__init__(self)
        self.docs = docs
        self.errors = errors


class InvalidAttachment(CouchError):
    """ raised when attachment is invalid (bad size, ct, ..)"""


class MissingContent(CouchError):
    """ raised when the clone_app extract content from property failed"""
