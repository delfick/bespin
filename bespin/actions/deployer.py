from bespin.actions.builder import Builder
from bespin.errors import NoSuchStack

import logging
import time
import json

log = logging.getLogger("bespin.actions.deployer")

class Deployer(object):
    def deploy_stack(self, stack, stacks, made=None, ignore_deps=False):
        """Deploy a stack and all it's dependencies"""
        Builder().sanity_check(stack, stacks, ignore_deps=ignore_deps)

        made = made or {}

        if stack.name in made:
            return

        if stack.name not in stacks:
            raise NoSuchStack(looking_for=stack.name, available=stacks.keys())

        if not ignore_deps and not stack.ignore_deps:
            for dependency in stack.dependencies(stacks):
                self.deploy_stack(stacks[dependency], stacks, made=made, ignore_deps=True)

        # Should have all our dependencies now
        log.info("Making stack for '%s' (%s)", stack.name, stack.stack_name)
        self.build_stack(stack)
        made[stack.name] = True

        if any(stack.build_after):
            for dependency in stack.build_after:
                self.deploy_stack(stacks[dependency], stacks, made=made, ignore_deps=True)

        if stack.artifact_retention_after_deployment:
            self.clean_old_artifacts(stack)

        self.confirm_deployment(stack)

    def build_stack(self, stack):
        """Build a single stack"""
        if stack.suspend_actions:
            self.suspend_cloudformation_actions(stack)

        print("Building - {0}".format(stack.stack_name))
        print(json.dumps(stack.params_json_obj, indent=4))

        skip = False
        if stack.cloudformation.status.exists:
            if stack.skip_update_if_equivalent and all(check.resolve() for check in stack.skip_update_if_equivalent):
                log.info("Stack is determined to be the same, not updating")
                skip = True

        if not skip:
            stack.create_or_update()

        # Avoid race condition
        time.sleep(5)

        stack.cloudformation.wait(rollback_is_failure=True)
        stack.cloudformation.reset()

        if stack.suspend_actions:
            self.resume_cloudformation_actions(stack)

    def confirm_deployment(self, stack):
        """Confirm our deployment"""
        stack.check_sns()
        stack.check_url()

    def clean_old_artifacts(self, stack):
        """Clean up any old artifacts"""
        stack.find_missing_artifact_env()
        stack.artifacts.clean_old_artifacts(stack.s3, dry_run=stack.bespin.dry_run)

    def suspend_cloudformation_actions(self, stack):
        """Suspend the ScheduledActions for an AutoScaling group in the stack"""
        autoscaling_group_id = stack.sns_confirmation.autoscaling_group_id
        asg_physical_id = stack.physical_id_for(autoscaling_group_id)
        stack.ec2.suspend_processes(asg_physical_id)
        log.info("Suspended Processes on AutoScaling Group %s", asg_physical_id)

    def resume_cloudformation_actions(self, stack):
        """Resume the ScheduledActions for an AutoScaling group in the stack"""
        autoscaling_group_id = stack.sns_confirmation.autoscaling_group_id
        asg_physical_id = stack.physical_id_for(autoscaling_group_id)
        stack.ec2.resume_processes(asg_physical_id)
        log.info("Resumed Processes on AutoScaling Group %s", asg_physical_id)

