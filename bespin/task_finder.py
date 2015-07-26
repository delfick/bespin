"""
Responsible for finding tasks in the configuration and executing them
"""

from bespin.actions import available_actions, default_actions
from bespin.option_spec.task_objs import Task
from bespin.errors import BadTask

class TaskFinder(object):
    def __init__(self, collector):
        self.tasks = {}
        self.collector = collector

    def stack_finder(self, task):
        return getattr(self.tasks[task], "stack", self.collector.configuration['bespin'].chosen_stack)

    def task_runner(self, task, **kwargs):
        if task not in self.tasks:
            raise BadTask("Unknown task", task=task, available=self.tasks.keys())
        return self.tasks[task].run(self.collector, self.stack_finder(task), available_actions, self.tasks, **kwargs)

    def default_tasks(self):
        """Return default tasks"""
        return dict((name, Task(action=name, label="Bespin")) for name in default_actions)

    def find_tasks(self, overrides):
        """Find the custom tasks and record the associated stack with each task"""
        tasks = self.default_tasks()
        configuration = self.collector.configuration

        for stack in list(configuration["stacks"]):
            path = configuration.path(["stacks", stack, "tasks"], joined="stacks.{0}.tasks".format(stack))
            nxt = configuration.get(path, {})
            tasks.update(nxt)

        if overrides:
            tasks.update(overrides)

        self.tasks = tasks

