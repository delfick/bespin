from bespin.errors import NoSuchStack
from bespin.layers import Layers
from bespin import helpers as hp

import logging
import json

log = logging.getLogger("bespin.actions.builder")

class Builder(object):
    def sanity_check(self, stack, stacks, ignore_deps=False, checked=None):
        """Perform sanity check on this stack and all it's dependencies"""
        if checked is None:
            checked = []

        if stack.stack_name in checked:
            return

        log.info("Sanity checking %s", stack.key_name)
        stack.sanity_check()

        if not ignore_deps and not stack.ignore_deps:
            for dependency in stack.dependencies(stacks):
                self.sanity_check(stacks[dependency], stacks, ignore_deps, checked + [stack.stack_name])

        if any(stack.build_after):
            for dependency in stack.build_after:
                self.sanity_check(stacks[dependency], stacks, ignore_deps, checked + [stack.stack_name])

    def deploy_stack(self, stack, stacks, made=None, ignore_deps=False):
        """Deploy a stack and all it's dependencies"""
        self.sanity_check(stack, stacks, ignore_deps=ignore_deps)

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

    def layered(self, stacks, only_pushable=False):
        """Yield layers of stacks"""
        if only_pushable:
            operate_on = dict((stack, instance) for stack, instance in stacks.items() if instance.stack_index)
        else:
            operate_on = stacks

        layers = Layers(operate_on, all_stacks=stacks)
        layers.add_all_to_layers()
        return layers.layered

    def build_stack(self, stack):
        if stack.suspend_actions:
            self.suspend_cloudformation_actions(stack)

        print("Building - {0}".format(stack.stack_name))
        print(json.dumps(stack.params_json_obj, indent=4))
        if stack.skip_update_if_equivalent and all(check.resolve() for check in stack.skip_update_if_equivalent):
            log.info("Stack is determined to be the same, not updating")
        else:
            stack.create_or_update()

        stack.cloudformation.wait(rollback_is_failure=True)
        stack.cloudformation.reset()

        if stack.suspend_actions:
            self.resume_cloudformation_actions(stack)

    def publish_artifacts(self, stack):
        stack.find_missing_build_env()

        # Iterate over each artifact we need to build
        for key, artifact in stack.artifacts.items():
            # Gather our environment variables
            environment = dict(env.pair for env in artifact.build_env)

            # Create a temporary file to tar to
            with hp.a_temp_file() as temp_tar_file:
                # Make the artifact
                hp.generate_tar_file(temp_tar_file, artifact.commands + artifact.paths + artifact.files
                    , environment=environment
                    , compression=artifact.compression_type
                    )
                log.info("Finished generating artifact: {0}".format(key))

                # Upload the artifact
                s3_location = artifact.upload_to.format(**environment)
                if stack.bespin.dry_run:
                    log.info("DRYRUN: Would upload tar file to %s", s3_location)
                else:
                    stack.s3.upload_file_to_s3(temp_tar_file.name, s3_location)

    def confirm_deployment(self, stack):
        stack.check_sns()
        stack.check_url()

    def clean_old_artifacts(self, stack):
        # Find missing env before doing anything
        stack.find_missing_artifact_env()
        stack.artifacts.clean_old_artifacts(stack.s3, dry_run=stack.bespin.dry_run)

    def suspend_cloudformation_actions(self, stack):
        autoscaling_group_id = self.sns_confirmation.autoscaling_group_id
        asg_physical_id = stack.asg_physical_id_for(autoscaling_group_id)
        stack.ec2.suspend_processes(asg_physical_id)
        log.info("Suspended Processes on AutoScaling Group %s", asg_physical_id)

    def resume_cloudformation_actions(self, stack):
        autoscaling_group_id = stack.sns_confirmation.autoscaling_group_id
        asg_physical_id = stack.asg_physical_id_for(autoscaling_group_id)
        stack.ec2.resume_processes(asg_physical_id)
        log.info("Resumed Processes on AutoScaling Group %s", asg_physical_id)

