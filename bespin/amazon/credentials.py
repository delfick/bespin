from bespin.amazon.cloudformation import Cloudformation
from bespin.helpers import memoized_property
from bespin.errors import BespinError
from bespin.amazon.ec2 import EC2
from bespin.amazon.sqs import SQS
from bespin.amazon.kms import KMS
from bespin.amazon.s3 import S3

import boto.sts
import boto.iam
import boto.s3
import boto.sqs

from input_algorithms.spec_base import NotSpecified
import logging
import boto
import os

log = logging.getLogger("iam_syncr.amazon")

class Credentials(object):
    def __init__(self, region, account_id, assume_role):
        self.region = region
        self.account_id = account_id
        self.assume_role = assume_role
        self.clouds = {}

    def verify_creds(self):
        """Make sure our current credentials are for this account and set self.connection"""
        if getattr(self, "_verified", None):
            return

        if self.assume_role is not NotSpecified:
            self.assume()
            self._verified = True
            return

        log.info("Verifying amazon credentials")
        try:
            connection = boto.iam.connect_to_region(self.region)
        except boto.exception.NoAuthHandlerFound:
            raise BespinError("Export AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY before running this script (your aws credentials)")

        try:
            result = connection.list_roles(max_items=1)
        except boto.exception.BotoServerError as error:
            if error.status == 403:
                raise BespinError("Couldn't determine what account your credentials are from", error=error.message)
            else:
                raise

        roles = result["list_roles_response"]["list_roles_result"]["roles"]
        if not roles:
            raise BespinError("There are no roles in your account, I can't figure out the account id")

        amazon_account_id = roles[0]['arn'].split(":")[4]
        if int(self.account_id) != int(amazon_account_id):
            raise BespinError("Please use credentials for the right account", expect=self.account_id, got=amazon_account_id)

        self._verified = True

    def assume(self):
        log.info("Assuming role as aws:arn:iam::%s:%s", self.account_id, self.assume_role)

        for name in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SECURITY_TOKEN', 'AWS_SESSION_TOKEN']:
            if name in os.environ and not os.environ[name]:
                del os.environ[name]

        try:
            conn = boto.sts.connect_to_region(self.region)
        except boto.exception.NoAuthHandlerFound:
            raise BespinError("Export AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY before running this script (your aws credentials)")

        try:
            creds = conn.assume_role("arn:aws:iam::{0}:{1}".format(self.account_id, self.assume_role), "bespin")
        except boto.exception.BotoServerError as error:
            if error.status == 403:
                raise BespinError("Not allowed to assume role", error=error.message)
            else:
                raise

        creds_dict = creds.credentials.to_dict()

        os.environ['AWS_ACCESS_KEY_ID'] = creds_dict["access_key"]
        os.environ['AWS_SECRET_ACCESS_KEY'] = creds_dict["secret_key"]
        os.environ['AWS_SECURITY_TOKEN'] = creds_dict["session_token"]
        os.environ['AWS_SESSION_TOKEN'] = creds_dict["session_token"]

    @memoized_property
    def s3(self):
        self.verify_creds()
        return S3(self.region)

    @memoized_property
    def ec2(self):
        self.verify_creds()
        return EC2(self.region)

    @memoized_property
    def sqs(self):
        self.verify_creds()
        return SQS(self.region)

    @memoized_property
    def kms(self):
        self.verify_creds()
        return KMS(self.region)

    @memoized_property
    def iam(self):
        self.verify_creds()
        log.info("Using region [%s] for iam", self.region)
        return boto.iam.connect_to_region(self.region)

    def cloudformation(self, stack_name):
        self.verify_creds()
        if stack_name not in self.clouds:
            self.clouds[stack_name] = Cloudformation(stack_name, self.region)
        return self.clouds[stack_name]

