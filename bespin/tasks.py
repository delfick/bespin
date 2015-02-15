"""
The functionality itself for each task.

Each task is specified with the ``a_task`` decorator and indicates whether it's
necessary to provide the task with the object containing all the stacks and/or
one specific stack object.
"""

from bespin.amazon.credentials import Credentials
from bespin.errors import BespinError, BadOption
from bespin.actions.deployer import Deployer
from bespin.actions.builder import Builder
from bespin.actions.ssh import SSH

from input_algorithms.spec_base import NotSpecified
from textwrap import dedent
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
            desc = dedent(task.description or "").strip().split('\n')[0]
            print("\t{0}{1} :-: {2}".format(" " * (max_length-len(key)), key, desc))
        print("")

@a_task(needs_stacks=True)
def show(overview, configuration, stacks, **kwargs):
    """
    Show what stacks we have in layered order.

    When combined with the ``--flat`` option, the stacks are shown as a flat
    list instead of in layers.
    """
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
        instance_ids = stack.ssh.find_instance_ids(stack)
        stack.ec2.display_instances(instance_ids, address=stack.ssh.address)
    else:
        stack.ssh.ssh_into(artifact, configuration["$@"])

@a_task()
def bastion(overview, configuration, **kwargs):
    """SSH into the bastion"""
    stack = list(configuration["stacks"].keys())[0]
    configuration["stacks"][stack].ssh.ssh_into_bastion(configuration["$@"])

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
    print(stack.stack_name)
    print(json.dumps(stack.params_json_obj, indent=4))

@a_task(needs_stack=True, needs_credentials=True)
def outputs(overview, configuration, stacks, stack, **kwargs):
    """Print out the outputs"""
    print(json.dumps(stack.cloudformation.outputs, indent=4))

@a_task(needs_stack=True, needs_credentials=True)
def command_on_instances(overview, configuration, stacks, stack, artifact, **kwargs):
    """Run a shell command on all the instances in the stack"""
    if stack.command is NotSpecified:
        raise BespinError("No command was found to run")

    log.info("Running '%s' on all instances for the %s stack", stack.command, stack.stack_name)
    if artifact:
        ips = [artifact]
    else:
        ips = list(stack.ssh.find_ips(stack))

    if not ips:
        raise BespinError("Didn't find any instances to run the command on")
    log.info("Running command on the following ips: %s", ips)

    if configuration["bespin"].dry_run:
        log.warning("Dry-run, only gonna run hostname on the boxes")
        command = "hostname"
    else:
        command = stack.command

    bastion_key_path, instance_key_path = stack.ssh.chmod_keys()
    proxy = stack.ssh.proxy_options(bastion_key_path)
    extra_kwargs = {}
    if proxy:
        extra_kwargs = {"proxy": stack.ssh.bastion, "proxy_ssh_key": bastion_key_path, "proxy_ssh_user": stack.ssh.user}

    SSH(ips, command, stack.ssh.user, instance_key_path, **extra_kwargs).run()

@a_task(needs_stack=True, needs_credentials=True, needs_artifact=True)
def scale_instances(overview, configuration, stacks, stack, artifact, **kwargs):
    """Change the number of instances in the stack's auto_scaling_group"""
    if isinstance(artifact, int) or artifact.isdigit():
        artifact = int(artifact)
    else:
        raise BespinError("The number of instances must be an integer")

    if artifact > stack.instance_count_limit:
        raise BespinError("The instance_count_limit is smaller than the specified number of instances", limit=stack.instance_count_limit, wanted=artifact)

    group = stack.auto_scaling_group
    current_count = group.desired_capacity
    log.info("Changing the number of instances in the %s stack from %s to %s", stack.stack_name, current_count, artifact)

    if group.min_size > artifact:
        log.info("Changing min_size from %s to %s", group.min_size, artifact)
        group.min_size = artifact
    if group.max_size < artifact:
        log.info("Changing max_size from %s to %s", group.max_size, artifact)
        group.max_size = artifact
    group.update()

    group.set_capacity(artifact)

@a_task()
def become(overview, configuration, stacks, stack, artifact, **kwargs):
    """Print export statements for assuming an amazon iam role"""
    bespin = configuration['bespin']
    environment = bespin.environment
    if not environment:
        raise BadOption("Please specify an environment")

    if all(thing in ("", None, NotSpecified) for thing in (stack, artifact)):
        raise BespinError("Please specify your desired role as an artifact")

    if artifact:
        role = artifact
    else:
        role = stack

    credentials = Credentials(bespin.region, configuration["environments"][environment].account_id, role)
    credentials.verify_creds()

    print("export AWS_ACCESS_KEY_ID={0}".format(os.environ['AWS_ACCESS_KEY_ID']))
    print("export AWS_SECRET_ACCESS_KEY={0}".format(os.environ['AWS_SECRET_ACCESS_KEY']))
    print("export AWS_SECURITY_TOKEN={0}".format(os.environ['AWS_SECURITY_TOKEN']))
    print("export AWS_SESSION_TOKEN={0}".format(os.environ['AWS_SESSION_TOKEN']))

