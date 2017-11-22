from bespin.errors import StackDoesntExist, BadStack, Throttled
from bespin.amazon.mixin import AmazonMixin
from bespin import helpers as hp

import botocore
import boto3
import datetime
import logging
import pytz
import time
import six
import os

log = logging.getLogger("bespin.amazon.cloudformation")

class StatusMeta(object):
    def __new__(cls, name, bases, attrs):
        attrs["name"] = name
        attrs["failed"] = name.endswith("FAILED")
        attrs["complete"] = name.endswith("COMPLETE")
        attrs["in_progress"] = name.endswith("IN_PROGRESS")
        attrs["cleanup_in_progress"] = name.endswith("CLEANUP_IN_PROGRESS")

        attrs["is_create"] = name.startswith("CREATE")
        attrs["is_delete"] = name.startswith("DELETE")
        attrs["is_update"] = name.startswith("UPDATE") and not name.startswith("UPDATE_ROLLBACK")
        attrs["is_rollback"] = name.startswith("ROLLBACK") or name.startswith("UPDATE_ROLLBACK")
        return type(name, bases, attrs)

class Status(object):
    exists = True
    statuses = {}

    @classmethod
    def find(kls, name):
        if name in kls.statuses:
            return kls.statuses[name]
        return six.add_metaclass(StatusMeta)(type(name, (Status, ), {}))

class NONEXISTANT(Status):
    exists = False

class CREATE_IN_PROGRESS(Status): pass
class CREATE_FAILED(Status): pass
class CREATE_COMPLETE(Status): pass

class ROLLBACK_IN_PROGRESS(Status): pass
class ROLLBACK_FAILED(Status): pass
class ROLLBACK_COMPLETE(Status): pass

class DELETE_IN_PROGRESS(Status): pass
class DELETE_FAILED(Status): pass
class DELETE_COMPLETE(Status): pass

class UPDATE_IN_PROGRESS(Status): pass
class UPDATE_COMPLETE_CLEANUP_IN_PROGRESS(Status): pass
class UPDATE_COMPLETE(Status): pass
class UPDATE_ROLLBACK_IN_PROGRESS(Status): pass
class UPDATE_ROLLBACK_FAILED(Status): pass
class UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS(Status): pass
class UPDATE_ROLLBACK_COMPLETE(Status): pass

# REVIEW_IN_PROGRESS only valid for CreateChangeSet with ChangeSetType=CREATE
class REVIEW_IN_PROGRESS(Status): pass

for kls in [Status] + Status.__subclasses__():
    with_meta = six.add_metaclass(StatusMeta)(kls)
    locals()[kls.__name__] = with_meta
    Status.statuses[kls.__name__] = with_meta

##BOTO3 TODO: refactor to use boto3 resources
class Cloudformation(AmazonMixin):
    def __init__(self, stack_name, region="ap-southeast-2"):
        self.region = region
        self.stack_name = stack_name

    @hp.memoized_property
    def conn(self):
        log.info("Using region [%s] for cloudformation (%s)", self.region, self.stack_name)
        return self.session.client('cloudformation', region_name=self.region)

    @hp.memoized_property
    def session(self):
        return boto3.session.Session(region_name=self.region)

    def reset(self):
        self._description = None

    def description(self, force=False):
        """Get the descriptions for the stack"""
        if not getattr(self, "_description", None) or force:
            with self.catch_boto_400(StackDoesntExist, "Couldn't find stack"):
                while True:
                    try:
                        with self.ignore_throttling_error():
                            response = self.conn.describe_stacks(StackName=self.stack_name)
                            self._description = response['Stacks'][0]
                            break
                    except Throttled:
                        log.info("Was throttled, waiting a bit")
                        time.sleep(0.5)
        return self._description

    @property
    def outputs(self):
        self.wait()
        description = self.description()
        if 'Outputs' in description:
            return dict((out['OutputKey'], out['OutputValue']) for out in description['Outputs'])
        else:
            return {}

    @property
    def status(self):
        force = False
        last_status = getattr(self, "_last_status", None)
        if last_status is None:
            self._last_status = datetime.datetime.now()
            force = True
        else:
            if self._last_status + datetime.timedelta(seconds=3) < datetime.datetime.now():
                force = True
                self._last_status = None

        try:
            description = self.description(force=force)
            return Status.find(description['StackStatus'])
        except StackDoesntExist:
            return NONEXISTANT

    def map_logical_to_physical_resource_id(self, logical_id):
        response = self.conn.describe_stack_resource(StackName=self.stack_name, LogicalResourceId=logical_id)
        return response['StackResourceDetail']["PhysicalResourceId"]

    def tags_from_dict(self, tags):
        """ helper to convert python dictionary into list of AWS Tag dicts """
        return [{'Key': k, 'Value': v} for k,v in tags.items()] if tags else []

    def params_from_dict(self, params):
        """ helper to convert python dictionary into list of CloudFormation Parameter dicts """
        return [{'ParameterKey': key, 'ParameterValue': value} for key, value in params.items()] if params else []

    def create(self, template_body, params, tags=None, policy=None, role_arn=None, termination_protection=False):
        log.info("Creating stack (%s)\ttags=%s", self.stack_name, tags)
        stack_tags = self.tags_from_dict(tags)
        stack_args = {
              'StackName': self.stack_name
            , 'TemplateBody': template_body
            , 'Parameters': params
            , 'Capabilities': ['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM']
            , 'DisableRollback': os.environ.get("DISABLE_ROLLBACK", 0) == "1"
            , "EnableTerminationProtection": termination_protection
            }
        if stack_tags: stack_args['Tags'] = stack_tags
        if policy: stack_args['StackPolicyBody'] = policy
        if role_arn: stack_args['RoleARN'] = role_arn
        self.conn.create_stack(**stack_args)
        return True

    def update(self, template_body, params, tags=None, policy=None, role_arn=None, termination_protection=False):
        log.info("Updating stack (%s)\ttags=%s", self.stack_name, tags)
        stack_tags = self.tags_from_dict(tags)
        stack_args = {
              'StackName': self.stack_name
            , 'TemplateBody': template_body
            , 'Parameters': params
            , 'Capabilities': ['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM']
            # NOTE: DisableRollback is not supported by UpdateStack. It is a property of the stack that can only be set during stack creation
            }
        if stack_tags: stack_args['Tags'] = stack_tags
        if policy: stack_args['StackPolicyBody'] = policy
        if role_arn: stack_args['RoleARN'] = role_arn

        changed = False

        with self.catch_boto_400(BadStack, "Couldn't update the stack", stack_name=self.stack_name):
            try:
                self.conn.update_stack(**stack_args)
                changed = True
            except botocore.exceptions.ClientError as error:
                if error.response['Error']['Message'] == "No updates are to be performed.":
                    log.info("No updates were necessary!")
                else:
                    raise

        with self.catch_boto_400(BadStack, "Couldn't update termination protection", stack_name=self.stack_name):
            info = self.conn.describe_stacks(StackName=self.stack_name)
            if info["Stacks"] and "EnableTerminationProtection" in info["Stacks"][0]:
                current = info["Stacks"][0]["EnableTerminationProtection"]
                if current != termination_protection:
                    log.info("Changing termination protection (%s)\ttermination_protection=%s", self.stack_name, termination_protection)
                    self.conn.update_termination_protection(StackName=self.stack_name, EnableTerminationProtection=termination_protection)
                    changed = True
            else:
                log.error("Failed to figure out if the stack currently has termination protection (%s)", self.stack_name)

        return changed

    def validate_template(self, filename):
        with self.catch_boto_400(BadStack, "Amazon says no", stack_name=self.stack_name, filename=filename):
            return self.conn.validate_template(TemplateBody=open(filename).read())

    ##BOTO3 TODO: can this be refactored with client.get_waiter?
    ##BOTO3 TODO: also consider client.get_paginator('describe_stack_events')
    def wait(self, timeout=1200, rollback_is_failure=False, may_not_exist=True):
        status = self.status
        if not status.exists and may_not_exist:
            return status

        last = datetime.datetime.now(pytz.utc)
        if status.failed:
            raise BadStack("Stack is in a failed state, it must be deleted first", name=self.stack_name, status=status)

        for _ in hp.until(timeout, step=15):
            if status.exists and status.complete:
                break

            log.info("Waiting for %s - %s", self.stack_name, status.name)
            if status.exists and not status.complete:
                status = self.status
            else:
                break

            description = self.description()

            events = []
            while True:
                try:
                    with self.ignore_throttling_error():
                        response = self.conn.describe_stack_events(StackName=self.stack_name)
                        events = response['StackEvents']
                        break
                except Throttled:
                    log.info("Was throttled, waiting a bit")
                    time.sleep(1)

            next_last = events[0]['Timestamp']
            for event in events:
                if event['Timestamp'] > last:
                    reason = event.get('ResourceStatusReason', '')
                    log.info("%s - %s %s (%s) %s", self.stack_name, event['ResourceType'], event['LogicalResourceId'], event['ResourceStatus'], reason)
            last = next_last

        status = self.status
        if status.failed or (rollback_is_failure and status.is_rollback) or not status.complete:
            raise BadStack("Stack failed to complete", final_status=status)

        return status

