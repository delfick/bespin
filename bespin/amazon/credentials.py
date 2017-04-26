from bespin.amazon.cloudformation import Cloudformation
from bespin.helpers import memoized_property
from bespin.errors import BespinError, ProgrammerError
from bespin.amazon.ec2 import EC2
from bespin.amazon.sqs import SQS
from bespin.amazon.kms import KMS
from bespin.amazon.s3 import S3
from bespin import VERSION

from input_algorithms.spec_base import NotSpecified
import logging
import botocore
import boto3
import os
import re

log = logging.getLogger("bespin.amazon.credentials")

class Credentials(object):
    def __init__(self, region, account_id, assume_role):
        self.region = region
        self.account_id = account_id
        self.assume_role = assume_role
        self.session = None
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
            self.session = boto3.session.Session(region_name=self.region)
            amazon_account_id = self.session.client('sts').get_caller_identity().get('Account')
            if int(self.account_id) != int(amazon_account_id):
                raise BespinError("Please use credentials for the right account", expect=self.account_id, got=amazon_account_id)
            self._verified = True
        except botocore.exceptions.NoCredentialsError:
            raise BespinError("Export AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY before running this script (your aws credentials)")
        except botocore.exceptions.ClientError as error:
            raise BespinError("Couldn't determine what account your credentials are from", error=error.message)

        if self.session is None or self.session.region_name != self.region:
            raise ProgrammerError("botocore.session created in incorrect region")

    def account_role_arn(self, role, partition='aws'):
        """Return full ARN for a role within the current account"""
        if not role or role.startswith("arn:aws"):
            return role
        if not role.startswith("role/"):
            role = "role/" + role
        return "arn:{0}:iam::{1}:{2}".format(partition, self.account_id, role)

    def assume(self):
        assumed_role = self.account_role_arn(self.assume_role)
        log.info("Assuming role as %s", assumed_role)

        for name in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SECURITY_TOKEN', 'AWS_SESSION_TOKEN']:
            if name in os.environ and not os.environ[name]:
                del os.environ[name]

        try:
            conn = boto3.client('sts', region_name=self.region)
            session_user = re.sub('[^\w+=,.@-]+', '', os.environ.get("USER", ""))
            if session_user:
                session_name = "{0}@bespin{1}".format(session_user, VERSION)
            else:
                session_name = "bespin{0}".format(VERSION)
            response = conn.assume_role(RoleArn=assumed_role, RoleSessionName=session_name)

            role = response['AssumedRoleUser']
            creds = response['Credentials']
            log.info("Assumed role (%s)", role['Arn'])
            self.session = boto3.session.Session(
                    aws_access_key_id=creds['AccessKeyId'],
                    aws_secret_access_key=creds['SecretAccessKey'],
                    aws_session_token=creds['SessionToken'],
                    region_name=self.region
            )

            os.environ['AWS_ACCESS_KEY_ID'] = creds["AccessKeyId"]
            os.environ['AWS_SECRET_ACCESS_KEY'] = creds["SecretAccessKey"]
            os.environ['AWS_SECURITY_TOKEN'] = creds["SessionToken"]
            os.environ['AWS_SESSION_TOKEN'] = creds["SessionToken"]
        except botocore.exceptions.NoCredentialsError:
            raise BespinError("Export AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY before running this script (your aws credentials)")
        except botocore.exceptions.ClientError as error:
            raise BespinError("Unable to assume role", error=error.message)

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
        return self.session.client('iam', region_name=self.region)

    def cloudformation(self, stack_name):
        self.verify_creds()
        if stack_name not in self.clouds:
            self.clouds[stack_name] = Cloudformation(stack_name, self.region)
        return self.clouds[stack_name]

