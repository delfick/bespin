import logging
import time
import boto

log = logging.getLogger("bespin.amazon.mixin")

class AmazonMixin(object):
    def catch_boto_400(self, errorkls, message, **info):
        """Turn a BotoServerError 400 into a BadAmazon"""
        attempt = 0
        while True:
            try:
                attempt += 1
                yield attempt
                break
            except boto.exception.BotoServerError as error:
                if error.code == "Throttling":
                    time.sleep(0.05)
                    continue

                if error.status == 400:
                    log.error("%s -(%s)- %s", message, error.code, error.message)
                    raise errorkls(message, error_code=error.code, error_message=error.message, **info)
                else:
                    raise
