from bespin.layers import Layers
from bespin import helpers as hp

import logging

log = logging.getLogger("bespin.operations.builder")

class Builder(object):
    def sanity_check(self, stack, stacks, ignore_deps=False, checked=None):
        """Perform sanity check on this stack and all it's dependencies"""
        checked = [] if checked is None else checked
        if stack.stack_name in checked:
            return

        log.info("Sanity checking %s", stack.key_name)
        stack.sanity_check()
        checked.append(stack.stack_name)

        if not ignore_deps and not stack.ignore_deps:
            for dependency in stack.dependencies(stacks):
                self.sanity_check(stacks[dependency], stacks, ignore_deps, checked)

        if any(stack.build_after):
            for dependency in stack.build_after:
                self.sanity_check(stacks[dependency], stacks, ignore_deps, checked)

    def layered(self, stacks, only_pushable=False):
        """Yield layers of stacks"""
        if only_pushable:
            operate_on = dict((stack, instance) for stack, instance in stacks.items() if instance.stack_index)
        else:
            operate_on = stacks

        layers = Layers(operate_on, all_stacks=stacks)
        layers.add_all_to_layers()
        return layers.layered

    def publish_artifacts(self, stack, artifacts=None):
        """Make and publish all the artifacts for a single stack"""
        stack.find_missing_build_env()

        if artifacts is None:
            artifacts = stack.artifacts.items()

        # Iterate over each artifact we need to build
        for key, artifact in artifacts:
            # Skip artifacts that are created elsewhere
            if artifact.not_created_here:
                continue

            # Gather our environment variables
            environment = dict(env.pair for env in stack.build_env)

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

    def clean_old_artifacts(self, stack):
        """Clean up any old artifacts"""
        stack.find_missing_env()
        environment = dict(env.pair for env in stack.env)
        stack.artifacts.clean_old_artifacts(stack.s3, environment, dry_run=stack.bespin.dry_run)

