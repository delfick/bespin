from bespin.errors import Throttled

from contextlib import contextmanager
import logging
import boto

log = logging.getLogger("bespin.amazon.mixin")

class AmazonMixin(object):
    @contextmanager
    def catch_boto_400(self, errorkls, message, **info):
        """Turn a BotoServerError 400 into a BadAmazon"""
        try:
            yield
        except boto.exception.BotoServerError as error:
            if error.status == 400:
                log.error("%s -(%s)- %s", message, error.code, error.message)
                raise errorkls(message, error_code=error.code, error_message=error.message, **info)
            else:
                raise

    @contextmanager
    def ignore_throttling_error(self):
        try:
            yield
        except boto.exception.BotoServerError as error:
            if error.status == 400 and error.code == "Throttling":
                raise Throttled()
            else:
                raise
