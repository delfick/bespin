"""
The functionality itself for each task.

Each task is specified with the ``a_task`` decorator and indicates whether it's
necessary to provide the task with the object containing all the stacks and/or
one specific stack object.
"""

from bespin.actions.deployer import Deployer
from bespin.actions.builder import Builder
import itertools
import logging
import shlex
import json
import os

log = logging.getLogger("bespin.tasks")

available_tasks = {}
class a_task(object):
    """Records a task in the ``available_tasks`` dictionary"""
    def __init__(self, needs_artifact=False, needs_stack=False, needs_stacks=False, needs_credentials=False):
        self.needs_artifact = needs_artifact
        self.needs_stack = needs_stack
        self.needs_stacks = needs_stack or needs_stacks
        self.needs_credentials = needs_credentials

    def __call__(self, func):
        available_tasks[func.__name__] = func
        func.needs_artifact = self.needs_artifact
        func.needs_stack = self.needs_stack
        func.needs_stacks = self.needs_stacks
        func.needs_credentials = self.needs_credentials
        return func

@a_task()
def list_tasks(overview, configuration, tasks, **kwargs):
    """List the available_tasks"""
    print("Available tasks to choose from are:")
    print("Use the --task option to choose one")
    print("")
    keygetter = lambda item: item[1].label
    tasks = sorted(tasks.items(), key=keygetter)
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

@a_task(needs_stack=True, needs_credentials=True)
def deploy(overview, configuration, stacks, stack, **kwargs):
    """Deploy a particular stack"""
    Deployer().deploy_stack(stack, stacks)

@a_task(needs_stack=True, needs_credentials=True)
def publish_artifacts(overview, configuration, stacks, stack, **kwargs):
    """Build and publish an artifact"""
    Builder().publish_artifacts(stack)

@a_task(needs_stack=True, needs_credentials=True)
def clean_old_artifacts(overview, configuration, stacks, stack, **kwargs):
    """Cleanup old artifacts"""
    Builder().clean_old_artifacts(stack)

@a_task(needs_stack=True, needs_credentials=True)
def confirm_deployment(overview, configuration, stacks, stack, **kwargs):
    """Confirm deployment via SNS notification for each instance and/or url checks"""
    Deployer().confirm_deployment(stack)

@a_task(needs_artifact=True)
def print_variable(overview, configuration, stacks, stack, artifact, **kwargs):
    """Prints out a variable from the stack"""
    print(configuration["bespin"].get_variable(artifact))

@a_task(needs_stack=True, needs_credentials=True)
def suspend_cloudformation_actions(overview, configuration, stacks, stack, **kwargs):
    """Suspends all schedule actions on a cloudformation stack"""
    Deployer().suspend_cloudformation_actions(stack)

@a_task(needs_stack=True, needs_credentials=True)
def resume_cloudformation_actions(overview, configuration, stacks, stack, **kwargs):
    """Resumes all schedule actions on a cloudformation stack"""
    Deployer().resume_cloudformation_actions(stack)

@a_task(needs_stack=True, needs_credentials=True)
def sanity_check(overview, configuration, stacks, stack, **kwargs):
    """Sanity check a stack and it's dependencies"""
    Builder().sanity_check(stack, stacks)
    log.info("All the stacks are sane!")

@a_task(needs_stack=True, needs_credentials=True)
def instances(overview, configuration, stacks, stack, artifact, **kwargs):
    """Find and ssh into instances"""
    if artifact is None:
        asg_physical_id = stack.cloudformation.map_logical_to_physical_resource_id(stack.ssh.autoscaling_group_name)
        stack.ec2.display_instances(asg_physical_id)
    else:
        stack.ssh.ssh_into(artifact, configuration["$@"])

@a_task(needs_stack=True)
def bastion(overview, configuration, stacks, stack, **kwargs):
    """SSH into the bastion"""
    stack.ssh.ssh_into_bastion(configuration["$@"])

@a_task(needs_credentials=True)
def execute(overview, configuration, **kwargs):
    """Exec a command using assumed credentials"""
    parts = shlex.split(configuration["$@"])
    configuration["bespin"].credentials.verify_creds()
    os.execvpe(parts[0], parts, os.environ)

@a_task(needs_credentials=True, needs_stack=True)
def tail(overview, configuration, stacks, stack, **kwargs):
    """Tail the deployment of a stack"""
    stack.cloudformation.wait()

@a_task(needs_stack=True)
def params(overview, configuration, stacks, stack, **kwargs):
    """Print out the params"""
    stack.find_missing_env()
    print(json.dumps(stack.params_json_obj, indent=4))

@a_task(needs_stack=True, needs_credentials=True)
def outputs(overview, configuration, stacks, stack, **kwargs):
    """Print out the outputs"""
    print(json.dumps(stack.cloudformation.outputs, indent=4))

