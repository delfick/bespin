from bespin.amazon.cloudformation import Cloudformation
from bespin.helpers import memoized_property
from bespin.errors import BespinError

import boto.iam
import boto.s3

import logging
import boto

log = logging.getLogger("iam_syncr.amazon")

class Credentials(object):
    def __init__(self, region, account_id):
        self.region = region
        self.account_id = account_id

    def verify_creds(self):
        """Make sure our current credentials are for this account and set self.connection"""
        if getattr(self, "_verified", None):
            return

        log.info("Verifying amazon credentials")
        try:
            connection = boto.iam.connect_to_region(self.region)
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
        if str(self.account_id) != str(amazon_account_id):
            raise BespinError("Please use credentials for the right account", expect=self.account_id, got=amazon_account_id)

        self._verified = True

    @memoized_property
    def s3(self):
        self.verify_creds()
        return boto.s3.connect_to_region(self.region)

    @memoized_property
    def iam(self):
        self.verify_creds()
        return boto.iam.connect_to_region(self.region)

    def cloudformation(self, stack_name, region):
        self.verify_creds()
        return Cloudformation(stack_name, region)

