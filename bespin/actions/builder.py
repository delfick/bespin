from bespin.amazon.s3 import delete_key_from_s3, list_keys_from_s3_path, upload_file_to_s3
from bespin.errors import NoSuchStack
from bespin.layers import Layers
from bespin import helpers as hp

import logging
import os

log = logging.getLogger("bespin.actions.builder")

class Builder(object):
    def deploy_stack(self, stack, stacks, credentials, made=None, ignore_deps=False):
        """Make us an stack"""
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
        print(stack.params_json_obj)

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
                hp.generate_tar_file(temp_tar_file, artifact.paths + artifact.files
                    , environment=environment
                    , compression=artifact.compression_type
                    )
                log.info("Finished generating artifact: {0}".format(key))

                # Upload the artifact
                upload_file_to_s3(credentials, temp_tar_file.name, artifact.upload_to.format(**environment))

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
