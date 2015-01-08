from six.moves.urllib.parse import urlparse
from contextlib import contextmanager
from collections import namedtuple
from six import StringIO
import logging
import boto
import math
import sys
import os

log = logging.getLogger("bespin.helpers")

S3Location = namedtuple("S3Location", ["bucket", "key", "full"])

def s3_location(value):
    """Return us an s3 location record type"""
    info = urlparse(value)
    if info.scheme != "s3":
        raise ValueError("S3 location must be a valid s3 url\tgot={0}".format(value))

    bucket = info.netloc
    if not bucket:
        raise ValueError("S3 location must be a valid s3 url\tgot={0}".format(value))

    key = info.path
    return S3Location(bucket, key, value)

@contextmanager
def a_multipart_upload(bucket, key):
    mp = None
    try:
        mp = bucket.initiate_multipart_upload(key)
        yield mp
    except:
        if mp:
            mp.cancel_upload()
        raise
    else:
        if mp:
            mp.complete_upload()

def upload_file_to_s3(credentials, source_filename, destination_path):
    source_file = open(source_filename, 'r')
    destination_file = s3_location(destination_path)

    source = os.path.abspath(source_file.name)
    source_size = os.stat(source).st_size
    log.info("Uploading from %s (%sb) to %s", source, source_size, destination_file.full)

    try:
        bucket = credentials.s3.get_bucket(destination_file.bucket)
    except boto.exception.S3ResponseError as error:
        if error.status in (404, 403):
            log.error("Bucket %s either doesn't exist or isn't available to you", destination_file.bucket)
            sys.exit(1)
        else:
            raise

    chunk = 5242880
    chunk_count = int(math.ceil(source_size / chunk))
    log.info("Uploading %s chunks", chunk_count + 1)

    try:
        with a_multipart_upload(bucket, destination_file.key) as mp:
            for i in range(chunk_count + 1):
                nxt = source_file.read(chunk)
                log.info("Uploading chunk %s", i + 1)
                mp.upload_part_from_file(StringIO(nxt), part_num=i + 1)
    except boto.exception.S3ResponseError as error:
        if error.status is 403:
            log.error("Seems you are unable to edit this location :(")
            sys.exit(1)
        else:
            raise

    log.info("Finished uploading")
