"""
Responsible for finding tasks in the configuration and executing them
"""

from bespin.tasks import available_tasks, default_tasks
from bespin.option_spec.task_objs import Task
from bespin.errors import BadTask

class TaskFinder(object):
    def __init__(self, collector, cli_args):
        self.tasks = {}
        self.cli_args = cli_args
        self.collector = collector
        self.configuration = self.collector.configuration

    def stack_finder(self, task):
        return getattr(self.tasks[task], "stack", self.configuration['bespin'].chosen_stack)

    def task_runner(self, task, **kwargs):
        if task not in self.tasks:
            raise BadTask("Unknown task", task=task, available=self.tasks.keys())
        return self.tasks[task].run(self.collector, self.cli_args, self.stack_finder(task), available_actions=available_tasks, tasks=self.tasks, **kwargs)

    def default_tasks(self):
        """Return default tasks"""
        def t(name, description=None, action=None, **options):
            if not action:
                action = name
            return (name, Task(action, description=description, options=options, label="Bespin"))
        base = dict(t(name) for name in default_tasks)
        return base

    def find_tasks(self, overrides):
        """Find the custom tasks and record the associated stack with each task"""
        tasks = self.default_tasks()
        configuration = self.configuration

        for stack in list(configuration["stacks"]):
            path = configuration.path(["stacks", stack, "tasks"], joined="stacks.{0}.tasks".format(stack))
            nxt = configuration.get(path, {})
            for task in nxt.values():
                task.specify_stack(stack)
            tasks.update(nxt)

        if overrides:
            tasks.update(overrides)

        self.tasks = tasks
