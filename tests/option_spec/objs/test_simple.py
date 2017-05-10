# coding: spec

from bespin.option_spec import stack_objs as objs

from tests.helpers import BespinCase

from noseOfYeti.tokeniser.support import noy_sup_setUp, noy_sup_tearDown
import mock
import os

describe BespinCase, "Static Variable":
    describe "resolve":
        it "just returns the value":
            value = mock.Mock(name="value")
            var = objs.StaticVariable(value)
            self.assertIs(var.resolve(), value)

describe BespinCase, "Dynamic Variable":
    describe "resolve":
        it "asks the stack to resolve the output":
            output = mock.Mock(name="output")
            resolved = mock.Mock(name="resolved")

            stack = mock.Mock(name="stack")
            stack.stack_json = {"Outputs": {"one": 1}}
            stack.cloudformation = mock.Mock(name="cloudformation", outputs={output: resolved})

            var = objs.DynamicVariable(stack, output)
            self.assertIs(var.resolve(), resolved)

describe BespinCase, "EnvironmentVariable":
    before_each:
        self.env_name = self.unique_val()
        self.fallback_val = self.unique_val()

    it "defaults default_val and set_val to None":
        env = objs.EnvironmentVariable(self.env_name)
        self.assertIs(env.default_val, None)
        self.assertIs(env.set_val, None)

    describe "pair":

        describe "Env name not in environment":
            before_each:
                assert self.env_name not in os.environ

            it "returns env_name and default_val if we have a default_val":
                for val in (self.fallback_val, ""):
                    env = objs.EnvironmentVariable(self.env_name, val, None)
                    self.assertEqual(env.pair, (self.env_name, val))

            it "returns env_name and set_val if we have a set_val":
                for val in (self.fallback_val, ""):
                    env = objs.EnvironmentVariable(self.env_name, None, val)
                    self.assertEqual(env.pair, (self.env_name, val))

            it "complains if we have no default_val":
                with self.fuzzyAssertRaisesError(KeyError, self.env_name):
                    env = objs.EnvironmentVariable(self.env_name)
                    env.pair

        describe "Env name is in environment":
            before_each:
                self.env_val = self.unique_val()
                os.environ[self.env_name] = self.env_val

            after_each:
                del os.environ[self.env_name]

            it "returns the value from the environment if default_val is set":
                env = objs.EnvironmentVariable(self.env_name, self.fallback_val, None)
                self.assertEqual(env.pair, (self.env_name, self.env_val))

            it "returns the set_val if set_val is set":
                env = objs.EnvironmentVariable(self.env_name, None, self.fallback_val)
                self.assertEqual(env.pair, (self.env_name, self.fallback_val))

            it "returns the value from the environment if no default or set val":
                env = objs.EnvironmentVariable(self.env_name)
                self.assertEqual(env.pair, (self.env_name, self.env_val))

