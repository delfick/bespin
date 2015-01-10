from bespin.amazon.cloudformation import Cloudformation
from bespin.helpers import memoized_property
from bespin.errors import BespinError

import boto.iam
import boto.s3

import logging
import boto

log = logging.getLogger("iam_syncr.amazon")

class Credentials(object):
    def __init__(self, region):
        self.region = region

    def verify_creds(self, account_id):
        """Make sure our current credentials are for this account and set self.connection"""
        log.info("Verifying amazon credentials")
        try:
            connection = self.iam
        except boto.exception.NoAuthHandlerFound:
            raise BespinError("Export AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY before running this script (your aws credentials)")

        try:
            result = connection.list_roles()
        except boto.exception.BotoServerError as error:
            if error.status == 403:
                raise BespinError("Your credentials aren't allowed to look at iam :(")
            else:
                raise

        roles = result["list_roles_response"]["list_roles_result"]["roles"]
        if not roles:
            raise BespinError("There are no roles in your account, I can't figure out the account id")

        amazon_account_id = roles[0]['arn'].split(":")[4]
        if str(account_id) != str(amazon_account_id):
            raise BespinError("Please use credentials for the right account", expect=account_id, got=amazon_account_id)

    @memoized_property
    def s3(self):
        return boto.s3.connect_to_region(self.region)

    @memoized_property
    def iam(self):
        return boto.iam.connect_to_region(self.region)

    def cloudformation(self, stack, region):
        return Cloudformation(stack, region)

