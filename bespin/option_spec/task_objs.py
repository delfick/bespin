"""
We have here the object representing a task.

Tasks contain a reference to the functionality it provides (in ``bespin.actions``)
as well as options that are used to override those in the stack it's attached to.
"""

from bespin.amazon.credentials import Credentials
from bespin.errors import BadOption

from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj
from option_merge import MergedOptions

class Task(dictobj):
    """
    Used to add extra options associated with the task and to start the action
    from ``bespin.actions``.

    Also responsible for complaining if the specified action doesn't exist.
    """
    fields = [("action", "run"), ("label", "Project"), ("options", None), ("overrides", None), ("description", "")]

    def setup(self, *args, **kwargs):
        super(Task, self).setup(*args, **kwargs)
        self.set_description()

    def specify_stack(self, stack):
        """Helper to set stack on the task object"""
        self.stack = stack

    def set_description(self, available_actions=None):
        if not self.description:
            if not available_actions:
                from bespin.actions import available_actions
            if self.action in available_actions:
                self.description = available_actions[self.action].__doc__

    def run(self, collector, stack, available_actions, tasks, **extras):
        """Run this task"""
        task_action = available_actions[self.action]
        self.set_description(available_actions)
        configuration = collector.configuration.wrapped()

        if self.options:
            if stack:
                configuration.update({"stacks": {stack: self.options}})
            else:
                configuration.update(self.options)

        configuration.update(configuration["cli_args"].as_dict(), source="<cli>")

        if self.overrides:
            overrides = {}
            for key, val in self.overrides.items():
                overrides[key] = val
                if isinstance(val, MergedOptions):
                    overrides[key] = dict(val.items())
            configuration.update(overrides)

        if task_action.needs_stack:
            environment = configuration["bespin"].environment
            if not environment:
                raise BadOption("Please specify an environment", available=list(configuration.get("environments", {}).keys()))
            if configuration["environments"].get(environment) is None:
                raise BadOption("No configuration found for specified environment", environment=environment, available=list(configuration["environments"].keys()))

            self.find_stack(stack, configuration)
            stack = configuration["stacks"][stack]

        bespin = configuration["bespin"]
        info = {"done": False}
        def set_credentials():
            if info["done"]:
                return
            info["done"] = True

            environment = configuration["bespin"].environment
            if not environment:
                raise BadOption("Please specify an environment", available=list(configuration["environments"].keys()))
            if environment not in configuration["environments"]:
                raise BadOption("Please specify a defined environment", available=list(configuration["environments"].keys()))
            region = configuration["environments"][environment].region

            no_assume_role = configuration["bespin"].no_assume_role
            if self.options and "no_assume_role" in self.options:
                no_assume_role = self.options["no_assume_role"]
            assume_role = NotSpecified if no_assume_role else configuration["bespin"].assume_role

            credentials = Credentials(
                  region
                , configuration["environments"][environment].account_id
                , assume_role
                )
            bespin.credentials = credentials
        bespin.set_credentials = set_credentials
        if task_action.needs_credentials:
            bespin.set_credentials()

        artifact = configuration["bespin"].chosen_artifact or None
        if task_action.needs_artifact and not artifact:
            raise BadOption("Please specify an artifact")

        from bespin.collector import Collector
        new_collector = Collector()
        new_collector.configuration = configuration
        new_collector.configuration_file = collector.configuration_file
        return task_action(collector, stack=stack, artifact=artifact, tasks=tasks, **extras)

    def find_stack(self, stack, configuration):
        """Complain if we don't have an stack"""
        stacks = configuration["stacks"]
        available = list(stacks.keys())

        if not stack:
            info = {}
            if available:
                info["available"] = available
            raise BadOption("Please use --stack to specify a stack to use", **info)

        if stack not in stacks:
            raise BadOption("No such stack", wanted=stack, available=available)

        return stacks

