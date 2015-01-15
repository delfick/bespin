from bespin.errors import BadS3Bucket

from six.moves.urllib.parse import urlparse
from contextlib import contextmanager
from collections import namedtuple
from filechunkio import FileChunkIO

import humanize
import logging
import boto
import sys
import os

from boto.s3.key import Key

log = logging.getLogger("bespin.amazon.s3")

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

def get_bucket(credentials, bucket_name):
    try:
        return credentials.s3.get_bucket(bucket_name)
    except boto.exception.S3ResponseError as error:
        if error.status in (404, 403):
            raise BadS3Bucket("Bucket either doesn't exist or isn't available to you", name=bucket_name)
        else:
            raise

def list_keys_from_s3_path(credentials, query_path):
    query = s3_location(query_path)
    bucket = get_bucket(credentials, query.bucket)
    return bucket.list(prefix="rca-contract")

def delete_key_from_s3(credentials, key, dry_run):
    if dry_run:
        print("Would delete {0}".format(key.name))
    else:
        print("Deleted {0}".format(key.name))
        key.delete()

def upload_file_to_s3(credentials, source_filename, destination_path):
    source_size = os.stat(source_filename).st_size
    if source_size > 30000000:
        upload_file_to_s3_in_parts(credentials, source_filename, destination_path)
    else:
        upload_file_to_s3_as_single(credentials, source_filename, destination_path)

def upload_file_to_s3_in_parts(credentials, source_filename, destination_path):
    source_file = open(source_filename, 'rb')
    destination_file = s3_location(destination_path)

    source = os.path.abspath(source_file.name)
    source_size = os.stat(source).st_size
    log.info("Uploading from %s (%s) to %s in parts", source, humanize.naturalsize(source_size), destination_file.full)

    bucket = get_bucket(credentials, destination_file.bucket)

    try:
        with a_multipart_upload(bucket, destination_file.key) as mp:
            for chunk, offset, length in determine_chunks(source_size, min_chunk=5242881):
                with FileChunkIO(source, 'r', offset=offset, bytes=length) as fp:
                    log.info("Uploading chunk %s (%s)", chunk+1, humanize.naturalsize(length))
                    mp.upload_part_from_file(fp, part_num=chunk+1)

    except boto.exception.S3ResponseError as error:
        if error.status is 403:
            log.error("Seems you are unable to edit this location :(")
            sys.exit(1)
        else:
            raise

    log.info("Finished uploading")

def determine_chunks(total_size, min_chunk=5242881):
    offset = 0
    offsets = []
    while offset < total_size:
        if total_size - offset < min_chunk:
            break
        offsets.append(offset)
        offset += min_chunk
    offsets.append(total_size)
    log.info("Broken up into %s chunks", len(offsets) - 1)

    for index, offset in enumerate(offsets[:-1]):
        nxt = offsets[index+1]
        yield index, offset, nxt - offset

def upload_file_to_s3_as_single(credentials, source_filename, destination_path):
    destination_file = s3_location(destination_path)

    source = os.path.abspath(source_filename)
    source_size = os.stat(source).st_size
    log.info("Uploading from %s (%s) to %s in one go", source, humanize.naturalsize(source_size), destination_file.full)

    bucket = get_bucket(credentials, destination_file.bucket)
    key = Key(bucket)
    key.name = destination_file.key
    key.set_contents_from_filename(source_filename)
    key.close()
