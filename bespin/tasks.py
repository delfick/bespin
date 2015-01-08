"""
The functionality itself for each task.

Each task is specified with the ``a_task`` decorator and indicates whether it's
necessary to provide the task with the object containing all the stacks and/or
one specific stack object.
"""

from bespin.actions.builder import Builder
import itertools
import logging

log = logging.getLogger("bespin.tasks")

available_tasks = {}
class a_task(object):
    """Records a task in the ``available_tasks`` dictionary"""
    def __init__(self, needs_stack=False, needs_stacks=False):
        self.needs_stack = needs_stack
        self.needs_stacks = needs_stack or needs_stacks

    def __call__(self, func):
        available_tasks[func.__name__] = func
        func.needs_stack = self.needs_stack
        func.needs_stacks = self.needs_stacks
        return func

@a_task()
def list_tasks(overview, configuration, **kwargs):
    """List the available_tasks"""
    print("Available tasks to choose from are:")
    print("Use the --task option to choose one")
    print("")
    keygetter = lambda item: item[1].label
    tasks = sorted(overview.find_tasks().items(), key=keygetter)
    for label, items in itertools.groupby(tasks, keygetter):
        print("--- {0}".format(label))
        print("----{0}".format("-" * len(label)))
        sorted_tasks = sorted(list(items), key=lambda item: len(item[0]))
        max_length = max(len(name) for name, _ in sorted_tasks)
        for key, task in sorted_tasks:
            print("\t{0}{1} :-: {2}".format(" " * (max_length-len(key)), key, task.description or ""))
        print("")

@a_task(needs_stacks=True)
def show(overview, configuration, stacks, **kwargs):
    """Show what stacks we have"""
    flat = configuration.get("bespin.flat", False)
    only_pushable = configuration.get("bespin.only_pushable", False)

    for index, layer in enumerate(Builder().layered(stacks, only_pushable=only_pushable)):
        if flat:
            for _, stack in layer:
                print(stack.stack_name)
        else:
            print("Layer {0}".format(index))
            for _, stack in layer:
                print("    {0}".format(stack.display_line()))
            print("")

@a_task(needs_stack=True)
def deploy(overview, configuration, stacks, stack, **kwargs):
    """Deploy a particular stack"""
    Builder().deploy_stack(stack, stacks)

@a_task(needs_stack=True)
def publish_artifacts(overview, configuration, stacks, stack, **kwargs):
    """Deploy a particular stack"""
    Builder().publish_artifacts(stack)

@a_task(needs_stack=True)
def clean_old_artifacts(overview, configuration, stacks, stack, **kwargs):
    """Deploy a particular stack"""
    Builder().clean_old_artifacts(stack)