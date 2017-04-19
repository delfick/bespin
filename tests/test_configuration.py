# coding: spec

from bespin.option_spec.bespin_specs import Bespin, Environment
from bespin.option_spec.stack_objs import Stack, StaticVariable
from bespin.option_spec.task_objs import Task
from bespin.collector import Collector

from tests.helpers import BespinCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms.spec_base import NotSpecified
from contextlib import contextmanager
from textwrap import dedent
import mock
import yaml
import uuid
import json
import nose
import sys
import os

describe BespinCase, "Collecting configuration":
    before_each:
        self.folder = self.make_temp_dir()
        self.docker_context = mock.Mock(name="docker_context")

    def make_config(self, options, folder=None, filename=None, is_json=False):
        if folder is None:
            folder = self.folder

        if filename is None:
            filename = str(uuid.uuid1())
        location = os.path.join(folder, filename)

        filetype = json if is_json else yaml
        filetype.dump(options, open(location, 'w'))
        return location

    @contextmanager
    def make_collector(self, config, home_dir_configuration=None, activate_converters=False):
        if home_dir_configuration is None:
            if hasattr(self, "home_dir_configuration"):
                home_dir_configuration = self.home_dir_configuration
            else:
                home_dir_configuration = self.make_config({})

        home_dir_configuration_location = mock.Mock(name="home_dir_configuration_location", spec=[])
        home_dir_configuration_location.return_value = home_dir_configuration
        collector_kls = type("CollectorSub", (Collector, ), {"home_dir_configuration_location": home_dir_configuration_location})
        collector = collector_kls()
        collector.configuration = collector.collect_configuration(config, mock.Mock(name="args_dict"))
        if activate_converters:
            collector.configuration.converters.activate()
        yield collector

    it "includes configuration from the home directory":
        config = self.make_config({"a":1, "b":2, "stacks": {"meh": {}}})
        home_config = self.make_config({"a":3, "c":4})
        with self.make_collector(config, home_config) as collector:
            self.assertEqual(sorted(collector.configuration.keys()), sorted(['a', 'b', 'c', 'config_root', 'stacks', 'getpass', 'args_dict', 'collector']))
            self.assertEqual(collector.configuration['a'], 1)
            self.assertEqual(collector.configuration['b'], 2)
            self.assertEqual(collector.configuration['c'], 4)

    it "sets up converters for bespin":
        config = self.make_config({"bespin": {}})
        with self.make_collector(config, activate_converters=True) as collector:
            self.assertIs(type(collector.configuration["bespin"]), Bespin)

    it "sets up converters for tasks":
        config = self.make_config({"stacks": {"blah": {"resources": [], "tasks": {"a_task": {}}}}})
        with self.make_collector(config, activate_converters=True) as collector:
            self.assertIs(type(collector.configuration["stacks.blah.tasks"]["a_task"]), Task)

    it "sets up converters for stacks":
        config = self.make_config({"environment": "dev", "environments": {"dev": {"account_id": "123"}}, "bespin": {"environment": "dev"}, "config_root": ".", "stacks": {"blah": {"params_yaml":self.make_config({"one":"two"}), "stack_json": self.make_config({"Resources": {}}, is_json=True), "resources": []}}})
        with self.make_collector(config, activate_converters=True) as collector:
            self.assertIs(type(collector.configuration["stacks.blah"]), Stack)

    it "merges environment into stack":
        config = {
              "environments":
              { "dev": {"account_id": "123", "vars": {"one": 1}}
              , 'staging': {"account_id": "456", "vars": {"one": 2}}
              }
            , "config_root": "."
            , "stacks":
              { "blah":
                { "params_yaml": self.make_config({"one":"two"})
                , "stack_json": self.make_config({"Resources": {}}, is_json=True)
                , "resources": []
                , "vars":
                  { "two": 2
                  }
                }
              }
            }

        config["environment"] = "dev"
        config["bespin"] = {"environment": "dev"}
        with self.make_collector(self.make_config(config), activate_converters=True) as collector:
            stack = collector.configuration["stacks.blah"]
            self.assertEqual(stack.vars()["two"].resolve(), '2')
            self.assertEqual(stack.vars()["one"].resolve(), '1')

        config["environment"] = "staging"
        config["bespin"] = {"environment": "staging"}
        with self.make_collector(self.make_config(config), activate_converters=True) as collector:
            stack = collector.configuration["stacks.blah"]
            self.assertEqual(stack.vars()["two"].resolve(), '2')
            self.assertEqual(stack.vars()["one"].resolve(), '2')

    it "converts environments":
        config = self.make_config({"environments": {"dev": {"account_id": "1231434"}, "staging": {"account_id": 87089, "vars": {"one": "ONE"}}}})
        with self.make_collector(config, activate_converters=True) as collector:
            environment = collector.configuration["environments"]
            self.assertEqual(type(environment["dev"]), Environment)
            self.assertEqual(environment["dev"].account_id, "1231434")
            self.assertEqual(type(environment["dev"].account_id), str)
            self.assertEqual(environment["staging"].account_id, 87089)
            self.assertEqual(type(environment["staging"].account_id), int)
            self.assertEqual(environment["staging"].vars.as_dict(), {"one": "ONE"})

    it "allows the special this_config_root formatter option to produce the config file where the option is defined":
        if sys.version.startswith("2.6."):
            raise nose.SkipTest("Can't have a zero length format field in python2.6")

        config1 = """
        ---
        bespin:
            environment: dev

            # extra_files is special and is already joined with the directory this config is in
            extra_files:
                - "one/two/stack.yml"


        vars:
            b_pointer: "{:this_config_dir}/b"

        stacks:
            one:
                vars:
                    watevs: 1
        """

        config2 = """
        ---

        environments:
            dev:
                account_id: "123"
                vars:
                    a_pointer: "{:this_config_dir}/a"
        """

        config3 = """
        ---

        bespin:
            # extra_files is special and is already joined with the directory this config is in
            extra_files:
                - "../envs.yml"

        stacks:
            one:
                stack_yaml: "{:this_config_dir}/c"

                vars:
                    d_pointer: "{:this_config_dir}/d"
        """

        stack_yaml = """
        ---

        options: here
        """

        root, record = self.setup_directory(
              { "bespin.yml": dedent(config1)
              , "b": ""
              , "one":
                { "a": ""
                , "envs.yml": dedent(config2)
                , "two":
                  { "stack.yml": dedent(config3)
                  , "c": dedent(stack_yaml)
                  , "d": ""
                  }
                }
              }
            )

        with self.make_collector(record["bespin.yml"]["/file/"], activate_converters=True) as collector:
            stack = collector.configuration[["stacks", "one"]]

        expected = {
              "watevs": StaticVariable('1')
            , "a_pointer": StaticVariable(record["one"]["a"]["/file/"])
            , "b_pointer": StaticVariable(record["b"]["/file/"])
            , "d_pointer": StaticVariable(record["one"]["two"]["d"]["/file/"])
            }

        self.assertEqual(stack["vars"](), expected)
        self.assertEqual(stack["stack_yaml"], dedent(stack_yaml))
