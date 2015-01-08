from bespin.errors import BadOption

from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj

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

class ArtifactFile(dictobj):
    fields = ["content", "path"]

