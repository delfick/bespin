from bespin.errors import NoSuchStack, BespinError
from bespin.operations.builder import Builder
from bespin import VERSION

from input_algorithms.spec_base import NotSpecified
from datetime import datetime
import logging
import time
import json
import sys
import os

log = logging.getLogger("bespin.operations.deployer")

class Deployer(object):
    def deploy_stack(self, stack, stacks, made=None, ignore_deps=False, checked=None, start=None, is_dependency=False):
        """Deploy a stack and all it's dependencies"""
        if start is None:
            start = datetime.utcnow()

        made = [] if made is None else made
        checked = [] if checked is None else checked
        if stack.name in made:
            return

        Builder().sanity_check(stack, stacks, ignore_deps=ignore_deps, checked=checked)
        made.append(stack.name)

        if stack.name not in stacks:
            raise NoSuchStack(looking_for=stack.name, available=stacks.keys())

        sent_by = "bespin=={0}({1})".format(VERSION, os.environ.get("USER", "<unknown_user>"))
        if not is_dependency and stack.notify_stackdriver:
            if stack.stackdriver is NotSpecified:
                raise BespinError("Need to specify stackdriver options when specifying notify_stackdriver")
            stack.stackdriver.create_event("{0}-{1} - Deploying cloudformation".format(stack.stack_name, stack.stackdriver.format_version(stack.env)), sent_by)

        if not ignore_deps and not stack.ignore_deps:
            for dependency in stack.dependencies(stacks):
                self.deploy_stack(stacks[dependency], stacks, made=made, ignore_deps=True, checked=checked, start=start, is_dependency=True)

        # Should have all our dependencies now
        log.info("Making stack for '%s' (%s)", stack.name, stack.stack_name)
        self.build_stack(stack)

        if any(stack.build_after):
            for dependency in stack.build_after:
                self.deploy_stack(stacks[dependency], stacks, made=made, ignore_deps=True, checked=checked, start=start, is_dependency=True)

        if not is_dependency and stack.notify_stackdriver:
            stack.stackdriver.create_event("{0}-{1} - Finished cloudformation".format(stack.stack_name, stack.stackdriver.format_version(stack.env)), sent_by)

        if stack.artifact_retention_after_deployment:
            Builder().clean_old_artifacts(stack)

        self.confirm_deployment(stack, start)

    def build_stack(self, stack):
        """Build a single stack"""
        if stack.suspend_actions and stack.cloudformation.status.exists:
            self.suspend_cloudformation_actions(stack)

        sys.stdout.write("Building - {0}\n".format(stack.stack_name))
    
        if stack.bespin.password_noecho:
            passwordnoecho = [self.maskpassword(c) for c in stack.params_json_obj]
            sys.stdout.write(json.dumps(passwordnoecho , indent=4))
        else:
            sys.stdout.write(json.dumps(stack.params_json_obj , indent=4))
        
        sys.stdout.write("\n")
        sys.stdout.flush()

        skip = False
        if stack.cloudformation.status.exists:
            if stack.skip_update_if_equivalent and all(check.resolve() for check in stack.skip_update_if_equivalent):
                log.info("Stack is determined to be the same, not updating")
                skip = True

        changed = False
        if not skip:
            changed = stack.create_or_update()

        if stack.bespin.dry_run:
            return

        if changed:

            # Avoid race condition
            time.sleep(5)

            stack.cloudformation.wait(timeout=stack.build_timeout, rollback_is_failure=True)
        else:
            stack.cloudformation.wait(timeout=stack.build_timeout)

        stack.cloudformation.reset()

        if stack.suspend_actions:
            self.resume_cloudformation_actions(stack)

    def maskpassword(self, params_json):
        maskpassword=json.loads(json.dumps(params_json))
        if maskpassword['ParameterKey'] == 'Password':
           maskpassword['ParameterValue'] = 'XXXXXXXXXXXX'
           return maskpassword
        return params_json

    def confirm_deployment(self, stack, start=None):
        """Confirm our deployment"""
        stack.confirm_the_deployment(start=start)

    def suspend_cloudformation_actions(self, stack):
        """Suspend the ScheduledActions for an AutoScaling group in the stack"""
        asg_physical_id = stack.physical_id_for(stack.auto_scaling_group_name)
        stack.ec2.suspend_processes(asg_physical_id)
        log.info("Suspended Processes on AutoScaling Group %s", asg_physical_id)

    def resume_cloudformation_actions(self, stack):
        """Resume the ScheduledActions for an AutoScaling group in the stack"""
        asg_physical_id = stack.physical_id_for(stack.auto_scaling_group_name)
        stack.ec2.resume_processes(asg_physical_id)
        log.info("Resumed Processes on AutoScaling Group %s", asg_physical_id)
