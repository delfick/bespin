from bespin.helpers import a_temp_file
from bespin.errors import BadOption

from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj

from tarfile import TarInfo
import codecs
import os

class Artifact(dictobj):
    fields = ["compression_type", "history_length", "location_var_name", "upload_to", "paths", "files", "build_env"]

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

    def add_to_tar(self, tar, environment):
        """Add everything in this ArtifactPath to the tar"""
        for full_path, tar_path in self:
            print(tar_path)
            tar.addfile(TarInfo(tar_path), fileobj=codecs.open(full_path.encode('utf-8'), encoding='utf-8'))

    def __iter__(self):
        """Iterate over the files in our host_path and yield (full_path, tar_path)"""
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

        with a_temp_file() as f:
            f.write(self.content.format(**environment).encode('utf-8'))
            f.close()
            print(self.path)
            tar.add(f.name.encode('utf-8'), self.path)

