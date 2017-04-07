from bespin.errors import Throttled

from contextlib import contextmanager
import logging
import botocore

log = logging.getLogger("bespin.amazon.mixin")

class AmazonMixin(object):
    @contextmanager
    def catch_boto_400(self, errorkls, message, **info):
        """Turn a boto HTTP 400 into a BadAmazon"""
        try:
            yield
        except botocore.exceptions.ClientError as error:
            code = error.response['ResponseMetadata']['HTTPStatusCode']
            if code == 400:
                log.error("%s -(%s)- %s", message, code, error.message)
                raise errorkls(message, error_code=code, error_message=error.message, **info)
            else:
                raise

    @contextmanager
    def ignore_throttling_error(self):
        try:
            yield
        except botocore.exceptions.ClientError as error:
            if error.response['Error']['Code'] == 'Throttling':
                raise Throttled()
            else:
                raise
