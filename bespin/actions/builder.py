from bespin.errors import NoSuchStack
from bespin.layers import Layers
from bespin import helpers as hp
from bespin import aws_helpers as aws

import logging

log = logging.getLogger("bespin.actions.builder")

class Builder(object):
    def deploy_stack(self, stack, stacks, made=None, ignore_deps=False):
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

    def publish_artifacts(self, stack):
        # Iterate over each artifact we need to build
        for key, artifact in stack.artifacts.items():
            # Check we are not missing any env vars
            artifact.find_missing_env()

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
                aws.upload_file_to_s3(temp_tar_file.name, artifact.upload_to.format(**environment))

    def clean_old_artifacts(self, stack):
        # Iterate over each artifact we need to clean
        for key, artifact in stack.artifacts.items():
            # Check we are not missing any env vars
            artifact.find_missing_env()

            # Clean it
            print(artifact.history_length)
