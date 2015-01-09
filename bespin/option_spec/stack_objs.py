from bespin.errors import MissingOutput, BadOption

from input_algorithms.dictobj import dictobj
import json
import six
import os

class Stack(dictobj):
    fields = [
          "bespin", "name", "key_name", "environment", "stack_json", "params_json"
        , "vars", "stack_name", "env", "build_after", "ignore_deps", "artifacts"
        ]

    def dependencies(self, stacks):
        for value in self.vars.values():
            if hasattr(value, "stack") and not isinstance(value.stack, six.string_types):
                yield value.stack.key_name

    @property
    def build_after(self):
        for stack in self._build_after:
            if isinstance(stack, six.string_types):
                yield stack
            else:
                yield stack.key_name

    @build_after.setter
    def build_after(self, val):
        self._build_after = val

    def display_line(self):
        return "Stack {0}".format(self.stack_name)

    def find_missing_env(self):
        """Find any missing environment variables"""
        missing = []
        for e in self.env:
            if e.default_val is None and e.set_val is None:
                if e.env_name not in os.environ:
                    missing.append(e.env_name)

        if missing:
            raise BadOption("Some environment variables aren't in the current environment", missing=missing)

    def resolve_output(self, output_name):
        outputs = self.outputs
        if output_name not in self.outputs:
            raise MissingOutput(wanted=output_name, available=outputs.keys())
        return self.outputs[output_name]

    @property
    def outputs(self):
        if not hasattr(self, "_outputs"):
            self._outputs = {}
        return self._outputs

    @property
    def params_json_obj(self):
        with open(self.params_json) as fle:
            params = fle.read()

        for thing in (self.vars.items(), [env.pair for env in self.env], self.artifact_vars):
            for var, value in thing:
                key = "XXX_{0}_XXX".format(var.upper())
                if key in params:
                    if not isinstance(value, six.string_types):
                        value = value.resolve()
                    params = params.replace(key, value)

        return json.loads(params)

    @property
    def artifact_vars(self):
        for name, artifact in self.artifacts.items():
            for var, value in artifact.vars:
                value = value.format(**dict(env.pair for env in self.env))
                yield var, value

class StaticVariable(dictobj):
    fields = ["value"]

    def resolve(self):
        return self.value

class DynamicVariable(dictobj):
    fields = ["stack", "output"]

    def resolve(self):
        return self.stack.resolve_output(self.output)

class Environment(dictobj):
    """A single environment variable, and it's default or set value"""
    fields = ["env_name", ("default_val", None), ("set_val", None)]

    @property
    def pair(self):
        """Get the name and value for this environment variable"""
        if self.set_val is not None:
            return self.env_name, self.set_val
        elif self.default_val is not None:
            return self.env_name, os.environ.get(self.env_name, self.default_val)
        else:
            return self.env_name, os.environ[self.env_name]

