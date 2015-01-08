# coding: spec

from bespin.option_spec.bespin_specs import Bespin
from bespin.option_spec.stack_objs import Stack
from bespin.option_spec.task_objs import Task
from bespin.executor import CliParser
from bespin.overview import Overview

from tests.helpers import BespinCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from option_merge import MergedOptions
from contextlib import contextmanager
import mock
import yaml
import uuid
import os

describe BespinCase, "Collecting configuration":
    before_each:
        self.folder = self.make_temp_dir()
        self.docker_context = mock.Mock(name="docker_context")

    def make_config(self, options, folder=None, filename=None):
        if folder is None:
            folder = self.folder

        if filename is None:
            filename = str(uuid.uuid1())
        location = os.path.join(folder, filename)

        yaml.dump(options, open(location, 'w'))
        return location

    @contextmanager
    def make_overview(self, config, home_dir_configuration=None, logging_handler=None, activate_converters=False):
        if home_dir_configuration is None:
            if hasattr(self, "home_dir_configuration"):
                home_dir_configuration = self.home_dir_configuration
            else:
                home_dir_configuration = self.make_config({})

        home_dir_configuration_location = mock.Mock(name="home_dir_configuration_location", spec=[])
        home_dir_configuration_location.return_value = home_dir_configuration
        overview_kls = type("OverviewSub", (Overview, ), {"home_dir_configuration_location": home_dir_configuration_location})
        overview = overview_kls(config, logging_handler=logging_handler)
        if activate_converters:
            overview.configuration.converters.activate()
        yield overview

    it "puts in mtime and stacks":
        config = self.make_config({"stacks": { "blah": {"resources": []}}})
        mtime = os.path.getmtime(config)
        with self.make_overview(config) as overview:
            self.assertIs(type(overview.configuration), MergedOptions)
            self.assertIs(type(overview.configuration["stacks"]), MergedOptions)
            self.assertEqual(overview.configuration['mtime'](), mtime)
            self.assertEqual(dict(overview.configuration['stacks'].items()), {"blah": overview.configuration["stacks.blah"]})
            self.assertEqual(sorted(overview.configuration.keys()), sorted(["mtime", "stacks"]))

    it "includes configuration from the home directory":
        config = self.make_config({"a":1, "b":2, "stacks": {"meh": {}}})
        home_config = self.make_config({"a":3, "c":4})
        with self.make_overview(config, home_config) as overview:
            self.assertEqual(sorted(overview.configuration.keys()), sorted(['a', 'b', 'c', 'mtime', 'stacks']))
            self.assertEqual(overview.configuration['a'], 1)
            self.assertEqual(overview.configuration['b'], 2)
            self.assertEqual(overview.configuration['c'], 4)

    it "sets up converters for overview":
        config = self.make_config({"bespin": {}})
        with self.make_overview(config, activate_converters=True) as overview:
            self.assertIs(type(overview.configuration["bespin"]), Bespin)

    it "sets up converters for tasks":
        config = self.make_config({"stacks": {"blah": {"resources": [], "tasks": {"a_task": {}}}}})
        with self.make_overview(config, activate_converters=True) as overview:
            self.assertIs(type(overview.configuration["stacks.blah.tasks"]["a_task"]), Task)

    it "sets up converters for stacks":
        config = self.make_config({"environment": "dev", "environments": {"dev": {}}, "bespin": {"environment": "dev"}, "config_root": ".", "stacks": {"blah": {"params_json":self.make_config({}), "stack_json": self.make_config({}), "resources": []}}})
        with self.make_overview(config, activate_converters=True) as overview:
            self.assertIs(type(overview.configuration["stacks.blah"]), Stack)

