# coding: spec

from bespin.option_spec import stack_specs as specs, stack_objs as objs

from tests.helpers import BespinCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms.spec_base import NotSpecified
from input_algorithms.meta import Meta
from option_merge import MergedOptions
import mock

describe BespinCase, "Var spec":
    before_each:
        self.meta = mock.Mock(name="meta", spec=Meta)

    it "creates a Static variable if only one item is given":
        self.assertEqual(specs.var_spec().normalise(self.meta, 1), objs.StaticVariable("1"))
        self.assertEqual(specs.var_spec().normalise(self.meta, "1"), objs.StaticVariable("1"))
        self.assertEqual(specs.var_spec().normalise(self.meta, ["1"]), objs.StaticVariable("1"))

    it "creates a Dynamic variable if only one item is given":
        stack = self.unique_val()
        output = self.unique_val()
        self.assertEqual(specs.var_spec().normalise(self.meta, [stack, output]), objs.DynamicVariable(stack, output))

describe BespinCase, "artifact_path_spec":
    before_each:
        self.meta = mock.Mock(name="artifact_path_spec")

    it "creates an artifact_path from the two items":
        host_path = self.unique_val()
        artifact_path = self.unique_val()
        self.assertEqual(specs.var_spec().normalise(self.meta, [host_path, artifact_path]), objs.DynamicVariable(host_path, artifact_path))

describe BespinCase, "Env spec":
    before_each:
        self.meta = mock.Mock(name="meta", spec=Meta)
        self.env_name = self.unique_val()
        self.fallback_val = self.unique_val()

    it "takes in just the env_name":
        assert ":" not in self.env_name
        assert "=" not in self.env_name

        made = specs.env_spec().normalise(self.meta, self.env_name)
        self.assertEqual(made.env_name, self.env_name)
        self.assertEqual(made.set_val, None)
        self.assertEqual(made.default_val, None)

    it "takes in env as a list with 1 item":
        assert ":" not in self.env_name
        assert "=" not in self.env_name

        made = specs.env_spec().normalise(self.meta, [self.env_name])
        self.assertEqual(made.env_name, self.env_name)
        self.assertEqual(made.set_val, None)
        self.assertEqual(made.default_val, None)

    it "takes in env as a list with 2 items":
        assert ":" not in self.env_name
        assert "=" not in self.env_name

        made = specs.env_spec().normalise(self.meta, [self.env_name, self.fallback_val])
        self.assertEqual(made.env_name, self.env_name)
        self.assertEqual(made.set_val, None)
        self.assertEqual(made.default_val, self.fallback_val)

    it "takes in env with blank default if suffixed with a colon":
        made = specs.env_spec().normalise(self.meta, self.env_name + ":")
        self.assertEqual(made.env_name, self.env_name)
        self.assertEqual(made.set_val, None)
        self.assertEqual(made.default_val, "")

    it "takes in env with blank set if suffixed with an equals sign":
        made = specs.env_spec().normalise(self.meta, self.env_name + "=")
        self.assertEqual(made.env_name, self.env_name)
        self.assertEqual(made.set_val, "")
        self.assertEqual(made.default_val, None)

    it "takes in default value if seperated by a colon":
        made = specs.env_spec().normalise(self.meta, self.env_name + ":" + self.fallback_val)
        self.assertEqual(made.env_name, self.env_name)
        self.assertEqual(made.set_val, None)
        self.assertEqual(made.default_val, self.fallback_val)

    it "takes in set value if seperated by an equals sign":
        made = specs.env_spec().normalise(self.meta, self.env_name + "=" + self.fallback_val)
        self.assertEqual(made.env_name, self.env_name)
        self.assertEqual(made.set_val, self.fallback_val)
        self.assertEqual(made.default_val, None)

