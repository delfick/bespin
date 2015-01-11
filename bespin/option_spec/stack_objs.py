from bespin.errors import MissingOutput, BadOption
from bespin.errors import StackDoesntExist
from bespin import helpers as hp

from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj
import logging
import json
import six
import os

log = logging.getLogger("bespin.option_spec.stack_objs")

class Stack(dictobj):
    fields = [
          "bespin", "name", "key_name", "environment", "stack_json", "params_json"
        , "vars", "stack_name", "env", "build_after", "ignore_deps", "artifacts"
        , "skip_update_if_equivalent"
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

    @property
    def cloudformation(self):
        if not hasattr(self, "_cloudformation"):
            self._cloudformation = self.bespin.credentials.cloudformation(self.stack_name, self.bespin.region)
        return self._cloudformation

    @property
    def params_json_obj(self):
        if self.params_json is NotSpecified:
            return {}

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

    def create_or_update(self):
        log.info("Creating or updating the stack (%s)", self.stack_name)
        status = self.cloudformation.status
        if status.failed:
            raise BadStack("Stack is in a failed state, it must be deleted first", name=self.stack_name, status=status)

        for _ in hp.until(timeout=500, step=2):
            if status.exists and not status.complete:
                log.info("Waiting for %s - %s", self.stack_name, status.name)
                status = self.cloudformation.status
            else:
                break

        if not status.exists:
            log.info("No existing stack, making one now")
        elif status.complete:
            log.info("Found existing stack, doing an update")
        else:
            raise BadStack("Stack could not be updated", name=self.stack_name, status=status.name)

class StaticVariable(dictobj):
    fields = ["value"]

    def resolve(self):
        return self.value

class DynamicVariable(dictobj):
    fields = ["stack", "output", ("credentials", None), ("region", None)]

    def resolve(self):
        if isinstance(self.stack, six.string_types):
            outputs = self.credentials.cloudformation(self.stack, self.region).outputs
        else:
            outputs = self.stack.cloudformation.outputs

        if self.output not in outputs:
            raise MissingOutput(wanted=self.output, available=outputs.keys())

        return outputs[self.output]

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

class Skipper(dictobj):
    fields = ["var1", "var2"]

    def resolve(self):
        try:
            v1 = self.var1().resolve()
        except StackDoesntExist:
            return False

        try:
            v2 = self.var2().resolve()
        except StackDoesntExist:
            return False

        return v1 and v2 and v1 == v2

