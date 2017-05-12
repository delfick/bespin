from bespin.helpers import memoized_property

from input_algorithms.spec_base import NotSpecified
import logging
import base64
import boto3
import json
import six

log = logging.getLogger("bespin.amazon.kms")

class KMS(object):
    def __init__(self, region="ap-southeast-2"):
        self.region = region

    @memoized_property
    def conn(self):
        log.info("Using region [%s] for kms", self.region)
        return self.session.client('kms', region_name=self.region)

    @memoized_property
    def session(self):
        return boto3.session.Session(region_name=self.region)

    def decrypt(self, crypto_text, encryption_context=None, grant_tokens=None):
        kms_args = {
            'CiphertextBlob': crypto_text,
        }
        if encryption_context and encryption_context is not NotSpecified:
            kms_args['EncryptionContext'] = encryption_context
        if grant_tokens and grant_tokens is not NotSpecified:
            kms_args['GrantTokens'] = grant_tokens

        return self.conn.decrypt(**kms_args)

    def encrypt(self, key_id, plain_text, encryption_context=None, grant_tokens=None):
        kms_args = {
            'KeyId': key_id,
            'Plaintext': plain_text,
        }
        if encryption_context and encryption_context is not NotSpecified:
            kms_args['EncryptionContext'] = encryption_context
        if grant_tokens and grant_tokens is not NotSpecified:
            kms_args['GrantTokens'] = grant_tokens

        return self.conn.encrypt(**kms_args)
