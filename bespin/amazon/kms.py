from bespin.helpers import memoized_property

from boto.kms.layer1 import KMSConnection
from boto.regioninfo import get_regions

from input_algorithms.spec_base import NotSpecified
import logging
import base64
import json
import six

log = logging.getLogger("bespin.amazon.kms")

class KMSFixed(KMSConnection):
    def encrypt(self, key_id, plaintext, encryption_context=None, grant_tokens=None):
        """
        Borrowed from boto sourcecode, waiting for https://github.com/boto/boto/pull/3051
        """
        if not isinstance(plaintext, six.binary_type):
            raise TypeError(
                "Value of argument ``plaintext`` "
                "must be of type %s." % six.binary_type)
        plaintext = base64.b64encode(plaintext)
        params = {'KeyId': key_id, 'Plaintext': plaintext.decode('utf-8'), }
        if encryption_context is not None:
            params['EncryptionContext'] = encryption_context
        if grant_tokens is not None:
            params['GrantTokens'] = grant_tokens
        response = self.make_request(action='Encrypt',
                                        body=json.dumps(params))
        if response.get('CiphertextBlob') is not None:
            response['CiphertextBlob'] = base64.b64decode(
                response['CiphertextBlob'].encode('utf-8'))
        return response

    def decrypt(self, ciphertext_blob, encryption_context=None,
                grant_tokens=None):
        """
        Borrowed from boto sourcecode, waiting for https://github.com/boto/boto/pull/3051
        """
        if not isinstance(ciphertext_blob, six.binary_type):
            raise TypeError(
                "Value of argument ``ciphertext_blob`` "
                "must be of type %s." % six.binary_type)
        ciphertext_blob = base64.b64encode(ciphertext_blob)
        params = {'CiphertextBlob': ciphertext_blob.decode('utf-8'), }
        if encryption_context is not None:
            params['EncryptionContext'] = encryption_context
        if grant_tokens is not None:
            params['GrantTokens'] = grant_tokens
        response = self.make_request(action='Decrypt',
                                     body=json.dumps(params))
        if response.get('Plaintext') is not None:
            response['Plaintext'] = base64.b64decode(
                response['Plaintext'].encode('utf-8'))
        return response

class KMS(object):
    def __init__(self, region="ap-southeast-2"):
        self.region = region

    @memoized_property
    def conn(self):
        log.info("Using region [%s] for kms", self.region)
        for region in get_regions('kms', connection_cls=KMSFixed):
            if region.name == self.region:
                return region.connect()

    def decrypt(self, crypto_text, encryption_context=None, grant_tokens=None):
        if encryption_context is NotSpecified:
            encryption_context = None
        if grant_tokens is NotSpecified:
            grant_tokens = None
        return self.conn.decrypt(crypto_text, encryption_context, grant_tokens)

    def encrypt(self, key_id, plain_text, encryption_context=None, grant_tokens=None):
        if encryption_context is NotSpecified:
            encryption_context = None
        if grant_tokens is NotSpecified:
            grant_tokens = None
        return self.conn.encrypt(key_id, plain_text, encryption_context, grant_tokens)

