"""
We have here the object representing a task.

Tasks contain a reference to the functionality it provides (in ``bespin.tasks``)
as well as options that are used to override those in the stack it's attached to.
"""

from bespin.errors import BadOption

from input_algorithms.dictobj import dictobj
from option_merge import MergedOptions

class Task(dictobj):
    """
    Used to add extra options associated with the task and to start the action
    from ``bespin.tasks``.

    Also responsible for complaining if the specified action doesn't exist.
    """
    fields = [("action", "run"), ("label", "Project"), ("options", None), ("overrides", None), ("description", "")]

    def run(self, overview, cli_args, stack, available_tasks=None):
        """Run this task"""
        if available_tasks is None:
            from bespin.tasks import available_tasks
        task_func = available_tasks[self.action]
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
        if task_func.needs_stacks:
            stacks = self.determine_stack(stack, overview, configuration, needs_stack=task_func.needs_stack)
            if stack:
                stack = stacks[stack]

        if stack:
            stack.find_missing_env()

        return task_func(overview, configuration, stacks=stacks, stack=stack)

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

