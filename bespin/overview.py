"""
This is the entry point of Bespin itself.

The overview object is responsible for collecting configuration, knowing default
tasks, and for starting the chosen task.
"""

from bespin.errors import BadConfiguration, BadTask, BadYaml
from bespin.option_spec.bespin_specs import BespinSpec
from bespin.option_spec.task_objs import Task
from bespin.tasks import available_tasks

from input_algorithms.dictobj import dictobj
from option_merge import MergedOptions
from input_algorithms.meta import Meta
from option_merge import Converter
from itertools import chain
import logging
import yaml
import os

log = logging.getLogger("bespin.executor")

class Overview(object):
    def __init__(self, configuration_file, logging_handler=None):
        self.logging_handler = logging_handler

        self.configuration = self.collect_configuration(configuration_file)
        self.configuration_folder = os.path.dirname(os.path.abspath(configuration_file))
        self.setup_logging_theme()

    def start(self, cli_args, available_tasks=None):
        """Do the bespin stuff"""
        if "stacks" not in self.configuration:
            raise BadConfiguration("Didn't find any stacks in the configuration")

        bespin = cli_args.pop("bespin")
        self.configuration.update(
            { "$@": bespin.get("extra", "")
            , "bespin": bespin
            , "config_root": self.configuration_folder
            , "environment": bespin.get("environment")
            }
        , source = "<cli>"
        )

        self.configuration.converters.activate()
        bespin = self.configuration["bespin"]
        tasks = self.find_tasks()
        task = bespin["chosen_task"]
        if task not in tasks:
            raise BadTask("Unknown task", task=task, available=tasks.keys())
        stack = getattr(tasks[task], "stack", bespin["chosen_stack"])

        tasks[task].run(self, cli_args, stack, available_tasks=available_tasks)

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

    def get_committime_or_mtime(self, location):
        """Get the commit time of some file or the modified time of of it if can't get from git"""
        return os.path.getmtime(location)

    def home_dir_configuration_location(self):
        """Return the location of the configuration in the user's home directory"""
        return os.path.expanduser("~/.bespin.yml")

    def collect_configuration(self, configuration_file):
        """Return us a MergedOptions with this configuration and any collected configurations"""
        errors = []

        result = self.read_yaml(configuration_file)

        bespin_spec = BespinSpec()
        configuration = MergedOptions(dont_prefix=[dictobj])

        home_dir_configuration = self.home_dir_configuration_location()
        sources = [home_dir_configuration, configuration_file]

        def make_mtime_func(source):
            """Lazily calculate the mtime to avoid wasted computation"""
            return lambda: self.get_committime_or_mtime(source)

        for source in sources:
            if source is None or not os.path.exists(source):
                continue

            try:
                result = self.read_yaml(source)
            except BadYaml as error:
                errors.append(error)
                continue

            result["mtime"] = make_mtime_func(source)

            if "stacks" in result:
                stacks = result.pop("stacks")
                stacks = dict(
                      (stack, MergedOptions.using(configuration.root(), val, converters=configuration.converters, source=source))
                      for stack, val in stacks.items()
                    )
                result["stacks"] = stacks

            configuration.update(result, dont_prefix=[dictobj], source=source)

            for stack in result.get('stacks', {}).keys():
                self.make_stack_converters(stack, configuration, bespin_spec)

        def convert_bespin(path, val):
            log.info("Converting %s", path)
            meta = Meta(path.configuration, [("bespin", "")])
            configuration.converters.started(path)
            return bespin_spec.bespin_spec.normalise(meta, val)

        bespin_converter = Converter(convert=convert_bespin, convert_path=["bespin"])
        configuration.add_converter(bespin_converter)

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
            environment_as_dict = configuration[["environments", environment]].as_dict()

            base = path.configuration.root().wrapped()
            everything = path.configuration.root().wrapped()

            base.update(config_as_dict)
            everything.update(config_as_dict)

            base.update(val_as_dict)
            everything[path] = val_as_dict

            base.update(environment_as_dict)
            everything.update(environment_as_dict)

            for thing in (base, everything):
                thing["bespin"] = configuration["bespin"]
                thing["environment"] = environment
                thing["configuration"] = configuration

            meta = Meta(everything, [("stacks", ""), (stack, "")])
            return bespin_spec.stack_spec.normalise(meta, base)

        converter = Converter(convert=convert_stack, convert_path=["stacks", stack])
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

    def default_tasks(self):
        """Return default tasks"""
        def t(name, description, action=None, **options):
            if not action:
                action = name
            return (name, Task(action, description=description, options=options, label="Bespin"))
        return dict([
              t("show", "Show the available stacks")
            , t("deploy", "Deploy a particular stack")
            , t("list_tasks", "List the available tasks")
            , t("clean_old_artifacts", "Cleans old artifacts from S3")
            , t("publish_artifacts", "Makes and uploads the artifacts for a stack to S3")
            ])

    def find_tasks(self, configuration=None):
        """Find the custom tasks and record the associated stack with each task"""
        if configuration is None:
            configuration = self.configuration

        tasks = self.default_tasks()
        for stack in list(configuration["stacks"]):
            path = configuration.path(["stacks", stack, "tasks"], joined="stacks.{0}.tasks".format(stack))
            nxt = configuration.get(path, {})
            for task in nxt.values():
                task.specify_stack(stack)
            tasks.update(nxt)

        return tasks
