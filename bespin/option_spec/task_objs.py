"""
We have here the object representing a task.

Tasks contain a reference to the functionality it provides (in ``bespin.tasks``)
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
    from ``bespin.tasks``.

    Also responsible for complaining if the specified action doesn't exist.
    """
    fields = [("action", "run"), ("label", "Project"), ("options", None), ("overrides", None), ("description", "")]

    def setup(self, *args, **kwargs):
        super(Task, self).setup(*args, **kwargs)
        self.set_description()

    def set_description(self, available_actions=None):
        if not self.description:
            if not available_actions:
                from bespin.tasks import available_tasks as available_actions
            if self.action in available_actions:
                self.description = available_actions[self.action].__doc__

    def run(self, overview, cli_args, stack, available_actions=None, tasks=None):
        """Run this task"""
        if available_actions is None:
            from bespin.tasks import available_tasks as available_actions

        task_action = available_actions[self.action]
        self.set_description(available_actions)
        configuration = MergedOptions.using(overview.configuration, dont_prefix=overview.configuration.dont_prefix, converters=overview.configuration.converters)

        if self.options:
            if stack:
                configuration.update({"stacks": {stack: self.options}})
            else:
                configuration.update(self.options)

        configuration.update(cli_args, source="<cli>")

        if self.overrides:
            overrides = {}
            for key, val in self.overrides.items():
                overrides[key] = val
                if isinstance(val, MergedOptions):
                    overrides[key] = dict(val.items())
            overview.configuration.update(overrides)

        stacks = None
        if task_action.needs_stacks:
            environment = configuration["bespin"].environment
            if not environment:
                raise BadOption("Please specify an environment")
            if configuration["environments"].get(environment) is None:
                raise BadOption("No configuration found for specified environment", environment=environment)

            stacks = self.determine_stack(stack, overview, configuration, needs_stack=task_action.needs_stack)
            if stack:
                stack = stacks[stack]

        bespin = configuration["bespin"]
        info = {"done": False}
        def set_credentials():
            if info["done"]:
                return
            info["done"] = True

            environment = configuration["bespin"].environment
            region = configuration["environments"][environment].region
            if not environment:
                raise BadOption("Please specify an environment")

            assume_role = NotSpecified if self.options.get("no_assume_role", False) or configuration["bespin"].no_assume_role else configuration["bespin"].assume_role
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

        return task_action(overview, configuration, stacks=stacks, stack=stack, artifact=artifact, tasks=tasks)

    def determine_stack(self, stack, overview, configuration, needs_stack=True):
        """Complain if we don't have an stack"""
        stacks = configuration["stacks"]

        available = None
        available = stacks.keys()

        if needs_stack:
            if not stack:
                info = {}
                if available:
                    info["available"] = list(available)
                raise BadOption("Please use --stack to specify a stack to use", **info)

            if stack not in stacks:
                raise BadOption("No such stack", wanted=stack, available=list(stacks.keys()))

        return stacks

    def specify_stack(self, stack):
        """Specify the stack this task belongs to"""
        self.stack = stack

