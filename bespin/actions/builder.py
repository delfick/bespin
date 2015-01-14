from bespin.amazon.s3 import delete_key_from_s3, list_keys_from_s3_path, upload_file_to_s3, upload_file_to_s3_as_single
from bespin.amazon.ec2 import get_instances_in_asg_by_lifecycle_state
from bespin.amazon.sqs import get_all_deployment_messages
from bespin.option_spec import stack_specs
from bespin.errors import NoSuchStack, BadDeployment
from bespin.layers import Layers
from bespin import helpers as hp

from input_algorithms.meta import Meta
import logging
import json
import os

log = logging.getLogger("bespin.actions.builder")

class Builder(object):
    def sanity_check(self, stack, stacks, ignore_deps=False, checked=None):
        """Check for missing environment variables in all the stacks"""
        if checked is None:
            checked = []

        if stack.stack_name in checked:
            return

        log.info("Sanity checking %s", stack.key_name)
        stack.find_missing_env()
        stack_specs.stack_json_spec().normalise(Meta({}, []), stack.stack_json_obj)
        if stack.params_json_obj:
            stack_specs.params_json_spec().normalise(Meta({}, []), stack.params_json_obj)

        if not ignore_deps and not stack.ignore_deps:
            for dependency in stack.dependencies(stacks):
                self.sanity_check(stacks[dependency], stacks, ignore_deps, checked + [stack.stack_name])

        if any(stack.build_after):
            for dependency in stack.build_after:
                self.sanity_check(stacks[dependency], stacks, ignore_deps, checked + [stack.stack_name])

    def deploy_stack(self, stack, stacks, credentials, made=None, ignore_deps=False):
        """Make us an stack"""
        self.sanity_check(stack, stacks, ignore_deps=ignore_deps)

        made = made or {}

        if stack.name in made:
            return

        if stack.name not in stacks:
            raise NoSuchStack(looking_for=stack.name, available=stacks.keys())

        if not ignore_deps and not stack.ignore_deps:
            for dependency in stack.dependencies(stacks):
                self.deploy_stack(stacks[dependency], stacks, credentials, made=made, ignore_deps=True)

            for dependency in stack.dependencies(stacks):
                stacks[dependency].cloudformation.wait()

        # Should have all our dependencies now
        log.info("Making stack for '%s' (%s)", stack.name, stack.stack_name)
        self.build_stack(stack)
        made[stack.name] = True

        if stack.sns_confirmation is not NotSpecified and stack.sns_confirmation.straight_after:
            stack.cloudformation.wait()
            self.confirm_deployment(stack, credentials)

        if any(stack.build_after):
            stack.cloudformation.wait()
            for dependency in stack.build_after:
                self.deploy_stack(stacks[dependency], stacks, credentials, made=made, ignore_deps=True)

            for dependency in stack.build_after:
                stacks[dependency].cloudformation.wait()

        stack.cloudformation.wait()
        if stack.sns_confirmation is not NotSpecified and not stack.sns_confirmation.straight_after:
            self.confirm_deployment(stack, credentials)

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
        print("Building - {0}".format(stack.stack_name))
        print(json.dumps(stack.params_json_obj, indent=4))
        if stack.skip_update_if_equivalent and all(check.resolve() for check in stack.skip_update_if_equivalent):
            log.info("Stack is determined to be the same, not updating")
        else:
            stack.create_or_update()

    def find_missing_build_env(self, stack):
        for artifact in stack.artifacts.values():
            artifact.find_missing_env()

    def publish_artifacts(self, stack, credentials):
        # Find missing env before doing anything
        self.find_missing_build_env(stack)

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
                upload_file_to_s3_as_single(credentials, temp_tar_file.name, artifact.upload_to.format(**environment))

    def confirm_deployment(self, stack, credentials):
        autoscaling_group_id = stack.sns_confirmation.autoscaling_group_id
        asg_physical_id = stack.cloudformation.map_logical_to_physical_resource_id(autoscaling_group_id)
        instances_to_check = get_instances_in_asg_by_lifecycle_state(credentials, asg_physical_id, lifecycle_state="InService")

        environment = dict(env.pair for env in stack.sns_confirmation.env)
        version_message = stack.sns_confirmation.version_message.format(**environment)

        failed = []
        success = []
        attempt = 0

        for _ in hp.until(action="Printing instance list"):
            messages = get_all_deployment_messages(credentials, stack.sns_confirmation.deployment_queue)

            # Look for success and failure in the messages
            for message in messages:
                log.info("Message received %s", message['output'])

                # Ignore the messages for instances outside this deployment
                if message['instance_id'] in instances_to_check:
                    if message['output'] == version_message:
                        log.info("Deployed instance %s", message['instance_id'])
                        success.append(message['instance_id'])
                    else:
                        log.info("Failed to deploy instance %s", message['instance_id'])
                        log.info("Failure Message: ", "%s", message['output'])
                        failed.append(message['instance_id'])

            # Stop trying if we have all the instances
            if set(failed + success) == set(instances_to_check):
                break

            # Record the iteration of checking for a valid deployment
            attempt += 1
            log.info("Completed attempt %s of checking for a valid deployment state", attempt)

        if success:
            log.info("Succeeded to deploy %s", success)
        if failed:
            log.info("Failed to deploy %s", failed)
            raise BadDeployment("")

        log.info("All instances have been confirmed to be deployed with version_message [%s]!", version_message)

    def clean_old_artifacts(self, stack, credentials):
        # Find missing env before doing anything
        self.find_missing_build_env(stack)

        # Iterate over each artifact we need to clean
        for key, artifact in stack.artifacts.items():
            environment = dict(env.pair for env in artifact.build_env)

            # Get contents of bucket
            artifact_path = os.path.dirname(artifact.upload_to.format(**environment))
            artifact_keys = list_keys_from_s3_path(credentials, artifact_path)

            # Get all the time stamps and determine the files to delete
            timestamps = list(map(lambda x: x.last_modified, artifact_keys))
            timestamps.sort()
            keys_to_del = timestamps[:-artifact.history_length]

            # Iterate through all the artifacts deleting any ones flagged for deletion
            for artifact_key in artifact_keys:
                if artifact_key.last_modified in keys_to_del:
                    log.info("Deleting artifact %s ", artifact_key.name)
                    delete_key_from_s3(credentials, artifact_key, stack.bespin.dry_run)
