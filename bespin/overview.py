"""
This is the entry point of Bespin itself.

The overview object is responsible for collecting configuration, knowing default
tasks, and for starting the chosen task.
"""

from bespin.errors import BadConfiguration, BadTask, BadYaml, BespinError
from bespin.formatter import MergedOptionStringFormatter
from bespin.option_spec.bespin_specs import BespinSpec
from bespin.option_spec.task_objs import Task
from bespin.tasks import available_tasks

from input_algorithms.spec_base import NotSpecified
from input_algorithms import spec_base as sb
from input_algorithms.dictobj import dictobj
from option_merge import MergedOptions
from input_algorithms.meta import Meta
from option_merge import Converter
from getpass import getpass
import logging
import yaml
import six
import os

log = logging.getLogger("bespin.executor")

class Overview(object):
    def __init__(self, configuration_file, logging_handler=None):
        self.logging_handler = logging_handler

        self.configuration_file = configuration_file
        self.configuration_folder = os.path.dirname(os.path.abspath(configuration_file))

        self.configuration = self.collect_configuration(configuration_file)
        self.setup_logging_theme()

    def clone(self, new_bespin_options=None):
        new_bespin = self.configuration["bespin"].clone()
        if new_bespin_options:
            new_bespin.update(new_bespin_options)

        new_bespin.set_credentials = self.configuration["bespin"].set_credentials
        if hasattr(self.configuration["bespin"], "credentials"):
            new_bespin.credentials = self.configuration["bespin"].credentials

        class NewOverview(Overview):
            def __init__(s):
                s.logging_handler = self.logging_handler
                s.configuration = self.collect_configuration(self.configuration_file)
                s.configuration_file = self.configuration_file
                s.configuration_folder = self.configuration_folder

        new_overview = NewOverview()
        new_cli_args = dict(self.configuration["cli_args"].items())
        new_cli_args["bespin"] = new_bespin
        new_overview.prepare(new_cli_args)
        return new_overview

    def prepare(self, cli_args, available_tasks=None):
        """Do the bespin stuff"""
        if "stacks" not in self.configuration:
            raise BadConfiguration("Didn't find any stacks in the configuration")
        if not self.configuration.get("environments"):
            raise BadConfiguration("Didn't find any environments configuration")

        bespin = cli_args.pop("bespin")
        environment = bespin.get("environment")

        info = {}
        stack_finder = lambda task: getattr(info["tasks"][task], "stack", bespin["chosen_stack"])
        def task_runner(task, **kwargs):
            if task not in tasks:
                raise BadTask("Unknown task", task=task, available=tasks.keys())
            info["tasks"][task].run(self, cli_args, stack_finder(task), available_actions=available_tasks, tasks=info["tasks"], **kwargs)

        self.configuration.update(
            { "$@": bespin.get("extra", "")
            , "bespin": bespin
            , "getpass": getpass
            , "overview": self
            , "cli_args": cli_args
            , "command": cli_args['command']
            , "config_root": self.configuration_folder
            , "environment": environment
            , "task_runner": task_runner
            , "stack_finder": stack_finder
            }
        , source = "<cli>"
        )

        self.configuration.converters.activate()
        if environment in self.configuration["environments"]:
            self.configuration.update({"region": self.configuration["environments"][environment].region})

        bespin = self.configuration["bespin"]

        task_overrides = {}
        for importer in bespin.extra_imports:
            importer.do_import(bespin, task_overrides)
        tasks = self.find_tasks(overrides=task_overrides)
        info["tasks"] = tasks

    def start(self, task=NotSpecified):
        """Start the chosen task"""
        task = self.configuration["bespin"].chosen_task if task is NotSpecified else task
        self.configuration["task_runner"](task)

    ########################
    ###   THEME
    ########################

    def setup_logging_theme(self):
        """
        Setup a logging theme

        Currently there is only ``light`` and ``dark`` which consists of a difference
        in color for INFO level messages.
        """
        if "term_colors" not in self.configuration:
            return

        if not getattr(self, "logging_handler", None):
            log.warning("Told to set term_colors but don't have a logging_handler to change")
            return

        colors = self.configuration.get("term_colors")
        if not colors:
            return

        if colors not in ("light", "dark"):
            log.warning("Told to set colors to a theme we don't have\tgot=%s\thave=[light, dark]", colors)
            return

        # Haven't put much effort into actually working out more than just the message colour
        if colors == "light":
            self.logging_handler._column_color['%(message)s'][logging.INFO] = ('cyan', None, False)
        else:
            self.logging_handler._column_color['%(message)s'][logging.INFO] = ('blue', None, False)

    ########################
    ###   CONFIG
    ########################

    def read_yaml(self, filepath):
        """Read in a yaml file and return as a python object"""
        try:
            if os.stat(filepath).st_size == 0:
                return {}
            return yaml.load(open(filepath))
        except yaml.parser.ParserError as error:
            raise BadYaml("Failed to read yaml", location=filepath, error_type=error.__class__.__name__, error="{0}{1}".format(error.problem, error.problem_mark))

    def home_dir_configuration_location(self):
        """Return the location of the configuration in the user's home directory"""
        return os.path.expanduser("~/.bespin.yml")

    def collect_configuration(self, configuration_file):
        """Return us a MergedOptions with this configuration and any collected configurations"""
        errors = []

        bespin_spec = BespinSpec()
        configuration = MergedOptions(dont_prefix=[dictobj])
        configuration["config_root"] = self.configuration_folder

        home_dir_configuration = self.home_dir_configuration_location()
        sources = [home_dir_configuration, configuration_file]

        done = set()
        def add_configuration(src):
            log.info("Adding configuration from %s", os.path.abspath(src))
            if os.path.abspath(src) in done:
                return
            else:
                done.add(os.path.abspath(src))

            if src is None or not os.path.exists(src):
                return

            try:
                result = self.read_yaml(src)
            except BadYaml as error:
                errors.append(error)
                return

            if not result:
                return

            configuration.update(result, dont_prefix=[dictobj], source=src)

            if "bespin" in configuration:
                if "extra_files" in configuration["bespin"]:
                    for extra in sb.listof(sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)).normalise(Meta(configuration, [("bespin", ""), ("extra_files", "")]), configuration["bespin"]["extra_files"]):
                        if os.path.abspath(extra) not in done:
                            if not os.path.exists(extra):
                                raise BadConfiguration("Specified extra file doesn't exist", extra=extra, source=src)
                            add_configuration(extra)

        for source in sources:
            add_configuration(source)

        for stack in configuration.get('stacks', {}).keys():
            self.make_stack_converters(stack, configuration, bespin_spec)

        def convert_bespin(path, val):
            log.info("Converting %s", path)
            meta = Meta(path.configuration, [("bespin", "")])
            configuration.converters.started(path)
            val["configuration"] = configuration.root()
            return bespin_spec.bespin_spec.normalise(meta, val)

        bespin_converter = Converter(convert=convert_bespin, convert_path=["bespin"])
        configuration.add_converter(bespin_converter)

        def convert_environments(path, val):
            log.info("Converting %s", path)
            meta = Meta(path.configuration, [("environments", "")])
            configuration.converters.started(path)
            return bespin_spec.environments_spec.normalise(meta, val)

        environments_converter = Converter(convert=convert_environments, convert_path=["environments"])
        configuration.add_converter(environments_converter)

        def convert_plans(path, val):
            log.info("Converting %s", path)
            meta = Meta(path.configuration, [("plans", "")])
            configuration.converters.started(path)
            return bespin_spec.plans_spec.normalise(meta, val)

        plans_converter = Converter(convert=convert_plans, convert_path=["plans"])
        configuration.add_converter(plans_converter)

        def convert_netscaler(path, val):
            log.info("Converting %s", path)
            meta = Meta(path.configuration, [("netscaler", "")])
            configuration.converters.started(path)
            return bespin_spec.netscaler_spec.normalise(meta, val)

        converter = Converter(convert=convert_netscaler, convert_path=["netscaler"])
        configuration.add_converter(converter)

        if errors:
            raise BadConfiguration("Some of the configuration was broken", _errors=errors)

        return configuration

    def make_stack_converters(self, stack, configuration, bespin_spec):
        """Make converters for this stack and add them to the configuration"""
        def convert_stack(path, val):
            log.info("Converting %s", path)
            configuration.converters.started(path)
            environment = configuration['bespin'].environment

            config_as_dict = configuration.as_dict(ignore=["stacks"])
            val_as_dict = val.as_dict(ignore=["stacks"])
            if not environment:
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
            spec = bespin_spec.tasks_spec(available_tasks)
            meta = Meta(path.configuration.root(), [('stacks', ""), (stack, ""), ('tasks', "")])
            configuration.converters.started(path)
            return spec.normalise(meta, val)

        converter = Converter(convert=convert_tasks, convert_path=["stacks", stack, "tasks"])
        configuration.add_converter(converter)

    ########################
    ###   TASKS
    ########################

    def default_tasks(self, has_netscaler=False):
        """Return default tasks"""
        def t(name, description=None, action=None, **options):
            if not action:
                action = name
            return (name, Task(action, description=description, options=options, label="Bespin"))
        base = dict(t(name) for name in [
              "tail"
            , "show"
            , "params"
            , "become"
            , "deploy"
            , "execute"
            , "outputs"
            , "bastion"
            , "downtime"
            , "instances"
            , "undowntime"
            , "list_tasks"
            , "deploy_plan"
            , "sanity_check"
            , "print_variable"
            , "scale_instances"
            , "encrypt_password"
            , "publish_artifacts"
            , "sanity_check_plan"
            , "confirm_deployment"
            , "clean_old_artifacts"
            , "command_on_instances"
            , "sync_netscaler_config"
            , "switch_dns_traffic_to"
            , "resume_cloudformation_actions"
            , "suspend_cloudformation_actions"
            ])
        if has_netscaler:
            for name, task in (t("enable_server_in_netscaler"), t("disable_server_in_netscaler")):
                base[name] = task
        return base

    def find_tasks(self, configuration=None, overrides=None):
        """Find the custom tasks and record the associated stack with each task"""
        if configuration is None:
            configuration = self.configuration

        tasks = self.default_tasks(has_netscaler="netscaler" in configuration)
        for stack in list(configuration["stacks"]):
            path = configuration.path(["stacks", stack, "tasks"], joined="stacks.{0}.tasks".format(stack))
            nxt = configuration.get(path, {})
            for task in nxt.values():
                task.specify_stack(stack)
            tasks.update(nxt)
        if overrides:
            tasks.update(overrides)

        return tasks
