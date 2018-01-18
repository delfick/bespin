from bespin.errors import BadS3Bucket, BespinError
from bespin import helpers as hp

from six.moves.urllib.parse import urlparse
from collections import namedtuple

from datetime import datetime

import botocore
import humanize
import logging
import boto3
import os

log = logging.getLogger("bespin.amazon.s3")

S3Location = namedtuple("S3Location", ["bucket", "key", "full"])

class S3(object):

    def __init__(self, region="ap-southeast-2"):
        self.region = region

    @hp.memoized_property
    def conn(self):
        log.info("Using region [%s] for S3 client", self.region)
        return self.session.client('s3', region_name=self.region)

    @hp.memoized_property
    def resource(self):
        log.info("Using region [%s] for S3 resource", self.region)
        return self.session.resource('s3', region_name=self.region)

    @hp.memoized_property
    def session(self):
        return boto3.session.Session(region_name=self.region)

    def s3_location(self, value):
        """Return us an s3 location record type"""
        info = urlparse(value)
        if info.scheme != "s3":
            raise ValueError("S3 location must be a valid s3 url\tgot={0}".format(value))

        bucket = info.netloc
        if not bucket:
            raise ValueError("S3 location must be a valid s3 url\tgot={0}".format(value))

        key = info.path
        return S3Location(bucket, key, value)

    def copy_key(self, frm, to):
        """Copy a key from <frm> to <to>"""
        frm_location = self.s3_location(frm)
        copy_source = {
            'Bucket': frm_location.bucket,
            'Key': frm_location.key[1:]
        }

        to_location = self.s3_location(to)
        bucket = self.get_bucket(to_location.bucket)

        log.info("Copying %s to %s", frm, to)
        bucket.copy(copy_source, to_location[1:])

    def wait_for(self, bucket, key, timeout, start=None):
        if start is None:
            start = datetime.utcnow()

        log.info("Looking for key with last_modified greater than %s", start)

        try:
            if key == '/':
                self.get_bucket(bucket).wait_until_exists()
                log.info("The bucket exists! and that is all we are looking for")
                return
            else:
                k = self.get_object(bucket, key)
                k.wait_until_exists(IfModifiedSince=start)
                log.info("Found key in the bucket\tbucket=%s\tkey=%s\tlast_modified=%s", bucket, key, k.last_modified)
                return
        except botocore.exceptions.BotoCoreError as error:
            raise BespinError("Couldn't find the s3 key", error=error.message)

        raise BespinError("Couldn't find the s3 key with a newer last modified")

    def get_bucket(self, bucket_name):
        return self.resource.Bucket(bucket_name)

    def get_object(self, bucket_name, key_name):
        return self.resource.Object(bucket_name, key_name)

    def list_keys_from_s3_path(self, query_path):
        query = self.s3_location(query_path)
        bucket = self.get_bucket(query.bucket)
        return bucket.objects.filter(Prefix=query.key[1:])

    def upload_file_to_s3(self, source_filename, destination_path):
        source = os.path.abspath(source_filename)
        source_size = os.stat(source).st_size
        dest = self.s3_location(destination_path)

        log.info("Uploading from %s (%s) to %s", source, humanize.naturalsize(source_size), dest.full)
        self.conn.upload_file(source, dest.bucket, dest.key[1:])
