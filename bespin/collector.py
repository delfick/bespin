"""
Collects then parses configuration files and verifies that they are valid.
"""

from bespin.errors import BadConfiguration, BadYaml, BespinError
from bespin.formatter import MergedOptionStringFormatter
from bespin.option_spec.bespin_specs import BespinSpec
from bespin.actions import available_actions
from bespin.task_finder import TaskFinder

from input_algorithms.spec_base import NotSpecified
from input_algorithms import spec_base as sb
from input_algorithms.dictobj import dictobj
from input_algorithms.meta import Meta

from option_merge.collector import Collector
from option_merge import MergedOptions
from option_merge import Converter

import logging
import yaml
import six
import os

log = logging.getLogger("bespin.collector")

class Collector(Collector):

    BadFileErrorKls = BadYaml
    BadConfigurationErrorKls = BadConfiguration

    def alter_clone_cli_args(self, new_collector, new_cli_args, new_bespin_options=None):
        new_bespin = self.configuration["bespin"].clone()
        if new_bespin_options:
            new_bespin.update(new_bespin_options)

        new_bespin.set_credentials = self.configuration["bespin"].set_credentials
        if hasattr(self.configuration["bespin"], "credentials"):
            new_bespin.credentials = self.configuration["bespin"].credentials

        new_cli_args["bespin"] = new_bespin

    def find_missing_config(self, configuration):
        """Used to make sure we have stacks and environments before doing anything"""
        if "stacks" not in self.configuration:
            raise self.BadConfigurationErrorKls("Didn't find any stacks in the configuration")
        if not self.configuration.get("environments"):
            raise self.BadConfigurationErrorKls("Didn't find any environments configuration")

    def extra_prepare(self, configuration, cli_args):
        """Called before the configuration.converters are activated"""
        bespin = cli_args.pop("bespin")
        environment = bespin.get("environment")

        bespin["configuration"] = configuration
        self.configuration.update(
            { "$@": bespin["extra"]
            , "bespin": bespin
            , "command": cli_args['command']
            , "environment": environment
            }
        , source = "<cli_args>"
        )

    def extra_prepare_after_activation(self, configuration, cli_args):
        """Called after the configuration.converters are activated"""
        environment = configuration["bespin"].environment

        available = list(self.configuration["environments"].keys())
        if environment is not NotSpecified and environment not in available:
            raise self.BadConfigurationErrorKls("Please choose a valid environment", available=available, wanted=environment)

        if environment in self.configuration["environments"]:
            self.configuration.update({"region": self.configuration["environments"][environment].region})

        bespin = self.configuration["bespin"]
        task_overrides = {}
        for importer in bespin.extra_imports:
            importer.do_import(bespin, task_overrides)

        task_finder = TaskFinder(self)
        self.configuration.update(
            { "stack_finder": task_finder.stack_finder
            , "task_runner": task_finder.task_runner
            }
        , source = "<code>"
        )
        task_finder.find_tasks(task_overrides)

    def home_dir_configuration_location(self):
        return os.path.expanduser("~/.bespin.yml")

    def start_configuration(self):
        """Create the base of the configuration"""
        return MergedOptions(dont_prefix=[dictobj])

    def read_file(self, location):
        """Read in a yaml file and return as a python object"""
        try:
            return yaml.load(open(location))
        except yaml.parser.ParserError as error:
            raise self.BadFileErrorKls("Failed to read yaml", location=location, error_type=error.__class__.__name__, error="{0}{1}".format(error.problem, error.problem_mark))

    def add_configuration(self, configuration, collect_another_source, done, result, src):
        """Used to add a file to the configuration, result here is the yaml.load of the src"""
        configuration.update(result, dont_prefix=[dictobj], source=src)

        if "bespin" in configuration:
            if "extra_files" in configuration["bespin"]:
                for extra in sb.listof(sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)).normalise(Meta(configuration, [("bespin", ""), ("extra_files", "")]), configuration["bespin"]["extra_files"]):
                    if os.path.abspath(extra) not in done:
                        if not os.path.exists(extra):
                            raise BadConfiguration("Specified extra file doesn't exist", extra=extra, source=src)
                        collect_another_source(extra)

    def extra_configuration_collection(self, configuration):
        """Hook to do any extra configuration collection or converter registration"""
        bespin_spec = BespinSpec()

        for stack in configuration.get('stacks', {}).keys():
            self.make_stack_converters(stack, configuration, bespin_spec)

        for path in ("bespin", "environments", "plans", "netscaler"):
            def make_converter(path):
                def converter(p, v):
                    log.info("Converting %s", p)
                    meta = Meta(p.configuration, [(path, "")])
                    spec = getattr(bespin_spec, "{0}_spec".format(path))
                    configuration.converters.started(p)
                    return spec.normalise(meta, v)
                return Converter(convert=converter, convert_path=[path])
            configuration.add_converter(make_converter(path))

    def make_stack_converters(self, stack, configuration, bespin_spec):
        """Make converters for this stack and add them to the configuration"""
        def convert_stack(path, val):
            log.info("Converting %s", path)
            configuration.converters.started(path)
            environment = configuration['bespin'].environment

            config_as_dict = configuration.as_dict(ignore=["stacks"])
            val_as_dict = val.as_dict(ignore=["stacks"])
            if not environment or environment is NotSpecified:
                raise BespinError("No environment was provided", available=list(configuration["environments"].keys()))

            env = configuration[["environments", environment]]
            if isinstance(env, six.string_types):
                environment_as_dict = configuration[["environments", env]].as_dict()
            else:
                environment_as_dict = configuration[["environments", environment]].as_dict()

            stack_environment_as_dict = {}
            if ["stacks", stack, environment] in configuration:
                stack_environment_as_dict = configuration["stacks", stack, environment].as_dict()

            base = path.configuration.root().wrapped()
            everything = path.configuration.root().wrapped()

            base.update(config_as_dict)
            everything[path].update(config_as_dict)

            base.update(val_as_dict)
            everything[path] = val_as_dict

            base.update(environment_as_dict)
            everything.update(environment_as_dict)

            base.update(stack_environment_as_dict)
            everything[path].update(stack_environment_as_dict)

            for thing in (base, everything):
                thing["bespin"] = configuration["bespin"]
                thing["environment"] = environment
                thing["configuration"] = configuration
                thing["__stack__"] = val
                thing["__environment__"] = configuration["environments"][environment]
                thing["__stack_name__"] = stack

            meta = Meta(everything, [("stacks", ""), (stack, "")])
            return bespin_spec.stack_spec.normalise(meta, base)

        converter = Converter(convert=convert_stack, convert_path=["stacks", stack])
        configuration.add_converter(converter)

        def convert_passwords(path, val):
            log.info("Converting %s", path)
            password = str(path)[len("passwords."):]
            configuration.converters.started(path)
            environment = configuration['bespin'].environment

            val_as_dict = configuration["passwords"][password].as_dict()
            if not environment:
                raise BespinError("No environment was provided", available=list(configuration["environments"].keys()))

            password_environment_as_dict = {}
            if ["passwords", password, environment] in configuration:
                password_environment_as_dict = configuration["passwords", password, environment].as_dict()

            base = MergedOptions(dont_prefix=path.configuration.dont_prefix, converters=path.configuration.converters)
            everything = path.configuration.root().wrapped()

            base.update(val_as_dict)
            everything[path] = val_as_dict

            base.update(password_environment_as_dict)
            everything[path].update(password_environment_as_dict)

            for thing in (base, everything):
                thing["__password__"] = val
                thing["__environment__"] = configuration["environments"][environment]

            meta = Meta(everything, [("passwords", ""), (password, "")])
            return bespin_spec.password_spec.normalise(meta, base)

        for key in configuration.get("passwords", {}):
            converter = Converter(convert=convert_passwords, convert_path=["passwords", key])
            configuration.add_converter(converter)

        def convert_tasks(path, val):
            spec = bespin_spec.tasks_spec(available_actions)
            meta = Meta(path.configuration.root(), [('stacks', ""), (stack, ""), ('tasks', "")])
            configuration.converters.started(path)
            tasks = spec.normalise(meta, val)
            for task in tasks.values():
                task.stack = stack
            return tasks

        converter = Converter(convert=convert_tasks, convert_path=["stacks", stack, "tasks"])
        configuration.add_converter(converter)

