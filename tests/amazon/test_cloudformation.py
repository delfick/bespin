# coding: spec

from bespin.amazon.cloudformation import Cloudformation, Status, NONEXISTANT, CREATE_COMPLETE, UPDATE_COMPLETE
from bespin.errors import StackDoesntExist

from tests.helpers import BespinCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from moto import mock_cloudformation, mock_sts
from textwrap import dedent
import botocore
import boto3
import nose
import os

describe BespinCase, "Status classes":
    it "have name equal to the class name":
        self.assertEqual(NONEXISTANT.name, "NONEXISTANT")
        self.assertEqual(Status.find("NONEXISTANT"), NONEXISTANT)
        self.assertEqual(UPDATE_COMPLETE.name, "UPDATE_COMPLETE")
        self.assertEqual(Status.find("UPDATE_COMPLETE"), UPDATE_COMPLETE)

    it "have helpful properties":
        self.assertEqual(NONEXISTANT.exists, False)
        self.assertEqual(UPDATE_COMPLETE.exists, True)

        self.assertEqual(NONEXISTANT.failed, False)
        self.assertEqual(UPDATE_COMPLETE.failed, False)

        self.assertEqual(NONEXISTANT.complete, False)
        self.assertEqual(UPDATE_COMPLETE.complete, True)

describe BespinCase, 'Cloudformation':
    before_each:
        # Make sure the environ doesn't already have credentials
        for key in ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AWS_SECURITY_TOKEN', 'AWS_DEFAULT_PROFILE', 'AWS_PROFILE', 'AWS_CREDENTIAL_FILE'):
            if key in os.environ:
                del os.environ[key]

    @mock_sts
    @mock_cloudformation
    it 'has appropriate properties':
        cf = Cloudformation('example_stack')
        self.assertEqual(cf.stack_name, 'example_stack')
        self.assertTrue(isinstance(cf.session, boto3.session.Session))
        self.assertTrue(isinstance(cf.conn, botocore.client.BaseClient))

    @mock_sts
    @mock_cloudformation
    it 'obtains credentials':
        cf = Cloudformation('_not_important')
        aws_creds = cf.session.get_credentials()

        # Moto provides the following credentials from 169.254.269.254
        self.assertEquals(aws_creds.access_key, 'test-key')
        self.assertEquals(aws_creds.secret_key, 'test-secret-key')
        self.assertEquals(aws_creds.token, 'test-session-token')

    @mock_sts
    @mock_cloudformation
    it 'uses correct region':
        cf = Cloudformation('_not_important', 'eu-central-1')
        self.assertEqual(cf.session.region_name, 'eu-central-1')
        self.assertEqual(cf.conn.meta.region_name, 'eu-central-1')

    @mock_sts
    @mock_cloudformation
    it 'converts tags and parameters':
        cf = Cloudformation('_not_important')
        tags = params = { 'a': 'alpha', 'b': 'beta' }

        stack_tags = cf.tags_from_dict(tags)
        stack_params = cf.params_from_dict(params)

        self.assertItemsEqual(stack_tags, [{'Value': 'alpha', 'Key': 'a'}, {'Value': 'beta', 'Key': 'b'}])
        self.assertItemsEqual(stack_params, [{'ParameterKey': 'a', 'ParameterValue': 'alpha'}, {'ParameterKey': 'b', 'ParameterValue': 'beta'}])

    @mock_sts
    @mock_cloudformation
    it 'knows when stacks dont exist':
        cf = Cloudformation('example_stack')

        self.assertEqual(cf.status, NONEXISTANT)
        self.assertFalse(cf.status.exists)

        with self.fuzzyAssertRaisesError(StackDoesntExist, "Couldn't find stack", error_code=400, error_message='Stack with id example_stack does not exist'):
            cf.description()
        with self.fuzzyAssertRaisesError(StackDoesntExist, "Couldn't find stack", error_code=400, error_message='Stack with id example_stack does not exist'):
            cf.outputs()

    # Note: Moto does not support yaml templates
    # https://github.com/spulec/moto/issues/912

    # EC2::InternetGateway chosen as moto has limited models it will mock
    sample_template_json = dedent("""
    {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "sample template",
        "Parameters": {
            "Input": {
                "Type": "String",
                "Default": "172.31.0.0/16"
            }
        },
        "Resources": {
            "Test": {
                "Type": "AWS::EC2::InternetGateway"
            }
        },
        "Outputs": {
            "StackName": {
                "Value": { "Ref": "AWS::StackName" }
            },
            "StackId": {
                "Value": { "Ref": "AWS::StackId" }
            },
            "Region": {
                "Value": { "Ref": "AWS::Region" }
            },
            "Test": {
                "Value": { "Ref": "Input" }
            }
        }
    }
    """)

    @mock_sts
    @mock_cloudformation
    it 'validates templates':
        cf = Cloudformation('new_stack')
        self.assertFalse(cf.status.exists)

        # Moto only partially implements validate_template
        # https://github.com/spulec/moto/issues/876
        with self.fuzzyAssertRaisesError(NotImplementedError):
            with self.a_temp_file() as filename:
                with open(filename, 'w') as fle:
                    fle.write(self.sample_template_json)
                result = cf.validate_template(filename)

    @mock_sts
    @mock_cloudformation
    it 'can create and update stack':
        cf = Cloudformation('new_stack', 'us-west-1')
        self.assertFalse(cf.status.exists)

        params = {'Input': '10.0.0.0/16'}
        tags = {'test': 'true'}
        stack_params = cf.params_from_dict(params)
        create_result = cf.create(self.sample_template_json, stack_params, tags=tags)

        self.assertTrue(create_result)
        self.assertEqual(cf.status, CREATE_COMPLETE)
        self.assertTrue(cf.status.exists)
        self.assertTrue(cf.status.is_create)
        self.assertTrue(cf.status.complete)

        self.assertTrue(cf.outputs)
        self.assertTrue(cf.description())

        orig_stackid = cf.description()['StackId']
        self.assertEqual(cf.outputs['StackId'], orig_stackid)
        self.assertEqual(cf.outputs['StackName'], 'new_stack')
        self.assertEqual(cf.outputs['Region'], 'us-west-1')
        self.assertEqual(cf.outputs['Test'], '10.0.0.0/16')

        resource = cf.map_logical_to_physical_resource_id('Test')
        self.assertTrue(isinstance(resource, str))
        self.assertTrue(resource.startswith('igw-'))

        cf.reset()

        # moto doesn't mock updates very well. don't expect much from here on
        params = {'Input': '10.255.255.0/24'}
        tags = {'tested': 'maybe'}
        stack_params = cf.params_from_dict(params)
        update_result = cf.update(self.sample_template_json, stack_params, tags=tags)

        self.assertTrue(update_result)
        self.assertEqual(cf.status, UPDATE_COMPLETE)
        self.assertTrue(cf.status.exists)
        self.assertTrue(cf.status.is_update)
        self.assertTrue(cf.status.complete)

        self.assertTrue(cf.outputs)
        self.assertTrue(cf.description())
        self.assertEqual(cf.outputs['StackId'], orig_stackid)
        self.assertEqual(cf.description()['StackId'], orig_stackid)
