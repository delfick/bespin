# coding: spec

from bespin.amazon.credentials import Credentials
from bespin.errors import BespinError

from tests.helpers import BespinCase

from input_algorithms.spec_base import NotSpecified
from moto import mock_sts
import os

# NOTE: moto uses account_id 123456789012
describe BespinCase, "Credentials":
    @mock_sts
    it "verifies credentials":
        credentials = Credentials('us-west-1', 123456789012, NotSpecified)
        try:
            credentials.verify_creds() # does not raise
        except Exception:
            self.fail("verify_creds() raised Exception unexpectedly!")
        self.assertEquals(credentials.account_id, 123456789012)
        self.assertEquals(credentials.region, 'us-west-1')
        self.assertTrue(credentials._verified)
        self.assertNotEqual(credentials.session, None)
        self.assertEquals(credentials.session.region_name, 'us-west-1')

        aws_creds = credentials.session.get_credentials()
        # NOTE: moto creds
        self.assertEquals(aws_creds.access_key, 'AKIAIOSFODNN7EXAMPLE')
        self.assertEquals(aws_creds.secret_key, 'aJalrXUtnFEMI/K7MDENG/bPxRfiCYzEXAMPLEKEY')
        self.assertEquals(aws_creds.token, 'BQoEXAMPLEH4aoAH0gNCAPyJxz4BlCFFxWNE1OPTgk5TthT+FvwqnKwRcOIfrRh3c/LTo6UDdyJwOOvEVPvLXCrrrUtdnniCEXAMPLE/IvU1dYUg2RVAJBanLiHb4IgRmpRV3zrkuWJOgQs8IZZaIv2BXIa2R4OlgkBN9bkUDNCJiBeb/AXlzBBko7b15fjrBs2+cTQtpZ3CYWFXG8C5zqx37wnOE49mRl/+OtkIKGO7fAE')

    @mock_sts
    it "verify_creds ensures account_id matches aws":
        credentials = Credentials('us-west-1', 987654321, NotSpecified)
        with self.fuzzyAssertRaisesError(BespinError, "Please use credentials for the right account", expect=987654321, got='123456789012'):
            credentials.verify_creds()

    @mock_sts
    it "assumes provided role":
        credentials = Credentials('us-west-1', 123456789012, 'example_role')
        try:
            credentials.verify_creds() # does not raise
        except Exception:
            self.fail("verify_creds() raised Exception unexpectedly!")
        self.assertTrue(credentials._verified)

        self.assertNotEqual(credentials.session, None)
        self.assertTrue('AWS_ACCESS_KEY_ID' in os.environ)
        self.assertTrue('AWS_SECRET_ACCESS_KEY' in os.environ)
        self.assertTrue('AWS_SECURITY_TOKEN' in os.environ)
        self.assertTrue('AWS_SESSION_TOKEN' in os.environ)

        aws_creds = credentials.session.get_credentials()
        self.assertEquals(aws_creds.access_key, os.environ['AWS_ACCESS_KEY_ID'])
        self.assertEquals(aws_creds.secret_key, os.environ['AWS_SECRET_ACCESS_KEY'])
        self.assertEquals(aws_creds.token, os.environ['AWS_SESSION_TOKEN'])
        self.assertEquals(credentials.session.region_name, 'us-west-1')

    @mock_sts
    it "account_role_arn":
        credentials = Credentials('us-west-1', 123456789012, NotSpecified)
        self.assertEquals(credentials.account_role_arn(None), None)
        self.assertEquals(credentials.account_role_arn('example'), 'arn:aws:iam::123456789012:role/example')
        self.assertEquals(credentials.account_role_arn('role/role_name'), 'arn:aws:iam::123456789012:role/role_name')
        self.assertEquals(credentials.account_role_arn('arn:aws:iam::000000:role/i_know_what_im_doing'), 'arn:aws:iam::000000:role/i_know_what_im_doing')
