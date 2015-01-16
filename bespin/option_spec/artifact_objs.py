from bespin.errors import BadOption, MissingFile
from bespin.processes import command_output
from bespin import helpers as hp

from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj

from tarfile import TarInfo
import shutil
import codecs
import os

class Artifact(dictobj):
    fields = [
          "compression_type", "history_length", "location_var_name"
        , "files", "build_env", "commands", "upload_to", "paths"
        ]

    @property
    def vars(self):
        if self.upload_to is not NotSpecified and self.location_var_name is not NotSpecified:
            yield (self.location_var_name, self.upload_to)

    def find_missing_env(self):
        """Find any missing environment variables"""
        missing = []
        for e in self.build_env:
            if e.default_val is None and e.set_val is None:
                if e.env_name not in os.environ:
                    missing.append(e.env_name)

        if missing:
            raise BadOption("Some environment variables aren't in the current environment", missing=missing)

class ArtifactPath(dictobj):
    fields = ["host_path", "artifact_path"]

    def add_to_tar(self, tar, environment=None):
        """Add everything in this ArtifactPath to the tar"""
        if environment is None:
            environment = {}

        for full_path, tar_path in self.files(environment):
            print(tar_path)
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

        for root, dirs, files in os.walk(self.host_path):
            for f in files:
                file_full_path = os.path.abspath(os.path.join(root, f))
                file_tar_path = file_full_path.replace(os.path.normpath(self.host_path), self.artifact_path)
                yield file_full_path, file_tar_path

class ArtifactFile(dictobj):
    fields = ["content", "path"]

    def add_to_tar(self, tar, environment=None):
        """Add this file to the tar"""
        if environment is None:
            environment = {}

        with hp.a_temp_file() as f:
            f.write(self.content.format(**environment).encode('utf-8'))
            f.close()
            print(self.path)
            tar.add(f.name, self.path)

class ArtifactCommand(dictobj):
    fields = ["copy", "modify", "command", "add_into_tar"]

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
                print(tar_path)
                tar.add(full_path, tar_path)

    def do_command(self, root, environment):
        command_output(self.command.format(**environment), cwd=root, timeout=600, verbose=True)

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

