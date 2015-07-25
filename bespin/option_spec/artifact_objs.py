from bespin.errors import BadOption, MissingFile, InvalidArtifact, BadCommand
from bespin.processes import command_output
from bespin import helpers as hp

from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj

import logging
import shutil
import sys
import os

log = logging.getLogger("bespin.option_spec.artifact_objs")

class ArtifactCollection(dictobj):
    fields = ['artifacts']

    def __iter__(self):
        return iter(self.artifacts)

    def items(self):
        return self.artifacts.items()

    def clean_old_artifacts(self, s3, environment, dry_run=True):
        # Iterate over each artifact we need to clean
        for key, artifact in self.artifacts.items():
            log.info("Cleaning old artifacts\tartifact=%s", key)
            # Get contents of bucket
            artifact_path = "{0}/".format(os.path.dirname(artifact.upload_to.format(**environment)))
            if artifact.cleanup_prefix is not NotSpecified:
                artifact_path = "{0}{1}".format(artifact_path, artifact.cleanup_prefix)
            artifact_keys = list(s3.list_keys_from_s3_path(artifact_path))

            # Get all the time stamps and determine the files to delete
            sorted_keys = sorted(artifact_keys, key=lambda x: x.last_modified)
            keys_to_del = sorted_keys[:-artifact.history_length]

            # Iterate through all the artifacts deleting any ones flagged for deletion
            for artifact_key in keys_to_del:
                log.info("Deleting artifact %s ", artifact_key.name)
                if dry_run:
                    log.info("DRYRUN: Would delete key")
                else:
                    artifact_key.delete()

class Artifact(dictobj):
    fields = {
          "paths": "Paths to copy from disk into the artifact"
        , "files": """
              Any files to add into the artifact

              For example::

                files:
                  - content: "{__stack__.vars.version}"
                    path: /artifacts/app/VERSION.txt
          """
        , "commands": "Commands that need to be run to generate content for the artifact"
        , "upload_to": "S3 path to upload the artifact to"
        , "not_created_here": "Boolean saying if this artifact is created elsewhere"
        , "cleanup_prefix": "The prefix to use when finding artifacts to clean up"
        , "history_length": """
              The number of artifacts to keep in s3

              .. note:: These only get purged if the stack has ``artifact_retention_after_deployment`` set
                to true or if the ``clean_old_artifacts`` task is run
          """
        , "compression_type": "The compression to use on the artifact"
        }

class ArtifactPath(dictobj):
    fields = ["host_path", "artifact_path", ("stdout", sys.stdout)]

    def add_to_tar(self, tar, environment=None):
        """Add everything in this ArtifactPath to the tar"""
        if environment is None:
            environment = {}

        for full_path, tar_path in self.files(environment):
            self.stdout.write(tar_path)
            self.stdout.write("\n")
            self.stdout.flush()
            tar.add(full_path, tar_path)

    def files(self, environment, prefix_path=None):
        """Iterate over the files in our host_path and yield (full_path, tar_path)"""
        host_path = self.host_path
        prefix_path = "/" if prefix_path is None else prefix_path
        while host_path and host_path.startswith("/"):
            host_path = host_path[1:]

        host_path = os.path.abspath(os.path.join(prefix_path, host_path.format(**environment)))
        artifact_path = os.path.abspath(self.artifact_path.format(**environment))

        if not os.path.exists(host_path):
            raise MissingFile("Expected to be able to copy in a path", path=host_path, artifact_path=artifact_path)

        if os.path.isfile(host_path):
            yield host_path, artifact_path
            return

        for root, dirs, files in os.walk(host_path, followlinks=True):
            for f in files:
                file_full_path = os.path.abspath(os.path.join(root, f))
                file_tar_path = file_full_path.replace(os.path.normpath(host_path), artifact_path, 1)
                yield file_full_path, file_tar_path

class ArtifactFile(dictobj):
    fields = ["content", "path", "task", "task_runner", ("stdout", sys.stdout)]

    def add_to_tar(self, tar, environment=None):
        """Add this file to the tar"""
        if environment is None:
            environment = {}

        with hp.a_temp_file() as f:
            if self.content is not NotSpecified:
                if getattr(self, "_no_more_formatting", False):
                    f.write(self.content.encode('utf-8'))
                else:
                    f.write(self.content.format(**environment).encode('utf-8'))
            else:
                self.task_runner(self.task, printer=f)

            f.close()
            self.stdout.write(self.path)
            self.stdout.write("\n")
            self.stdout.flush()
            tar.add(f.name, self.path)

class ArtifactCommand(dictobj):
    fields = ["copy", "modify", "command", "add_into_tar", ("timeout", 600), ("stdout", sys.stdout)]

    def add_to_tar(self, tar, environment=None):
        if environment is None:
            environment = {}

        with hp.a_temp_directory() as command_root:
            self.do_copy(command_root, environment)
            self.do_modify(command_root, environment)
            self.do_command(command_root, environment)
            self.do_copy_into_tar(command_root, environment, tar)

    def do_copy_into_tar(self, into, environment, tar):
        for path in self.add_into_tar:
            for full_path, tar_path in path.files(environment, prefix_path=into):
                self.stdout.write(tar_path)
                self.stdout.write("\n")
                self.stdout.flush()
                tar.add(full_path, tar_path)

    def do_command(self, root, environment):
        for cmd in self.command:
            output, status = command_output(cmd.format(**environment), cwd=root, timeout=self.timeout, verbose=True)
            if status != 0:
                raise BadCommand("Failed to run command", cmd=cmd.format(**environment), output=output, status=status)

    def do_modify(self, into, environment):
        for key, options in self.modify.items():
            path = os.path.join(into, key)
            if not os.path.exists(path):
                raise MissingFile("Expected a file to modify", path=path)

            if "append" in options:
                with open(path, "a") as fle:
                    fle.write("\n")
                    for append in options["append"]:
                        fle.write("{0}\n".format(append.format(**environment)))

    def do_copy(self, into, environment):
        for path in self.copy:
            for full_path, copy_path in path.files(environment):
                while copy_path.startswith("/"):
                    copy_path = copy_path[1:]
                copy_path = os.path.join(into, copy_path)
                if not os.path.exists(os.path.dirname(copy_path)):
                    os.makedirs(os.path.dirname(copy_path))
                shutil.copy(full_path, copy_path)

