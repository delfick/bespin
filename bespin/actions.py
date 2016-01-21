"""
The functionality itself for each task.

Each task is specified with the ``an_action`` decorator
"""

from bespin.errors import BespinError, BadOption, ProgrammerError
from bespin.option_spec.bespin_specs import valid_password_key
from bespin.option_spec.stack_specs import env_spec
from bespin.amazon.credentials import Credentials
from bespin.operations.downtimer import Downtimer
from bespin.operations.deployer import Deployer
from bespin.operations.builder import Builder
from bespin.operations.plan import Plan
from bespin.operations.ssh import SSH
from bespin.layers import Layers
from bespin import helpers as hp

from input_algorithms.spec_base import NotSpecified
from input_algorithms import spec_base as sb
from input_algorithms.meta import Meta
from textwrap import dedent
from getpass import getpass
import itertools
import logging
import base64
import shlex
import json
import sys
import os

log = logging.getLogger("bespin.tasks")

info = {"is_default": True}
default_actions = []
available_actions = {}

class an_action(object):
    """Records a task in the ``available_tasks`` dictionary"""
    def __init__(self, needs_artifact=False, needs_stack=False, needs_credentials=False):
        self.needs_artifact = needs_artifact
        self.needs_stack = needs_stack
        self.needs_credentials = needs_credentials

    def __call__(self, func):
        available_actions[func.__name__] = func
        func.needs_artifact = self.needs_artifact
        func.needs_stack = self.needs_stack
        func.needs_credentials = self.needs_credentials
        if info["is_default"]:
            default_actions.append(func.__name__)
        return func

def get_from_env(wanted):
    """Get environment variables from the env"""
    env = sb.listof(env_spec()).normalise(Meta({}, []), wanted)
    missing = [e.env_name for e in env if e.missing]
    if missing:
        raise BespinError("Missing environment variables", missing=missing)
    return dict(e.pair for e in env)

@an_action()
def list_tasks(collector, tasks, **kwargs):
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

@an_action()
def show(collector, **kwargs):
    """
    Show what stacks we have in layered order.

    When combined with the ``--flat`` option, the stacks are shown as a flat
    list instead of in layers.
    """
    configuration = collector.configuration
    flat = configuration.get("bespin.flat", False)
    only_pushable = configuration.get("bespin.only_pushable", False)

    stacks = configuration["stacks"]
    for index, layer in enumerate(Builder().layered(stacks, only_pushable=only_pushable)):
        if flat:
            for _, stack in layer:
                print(stack.stack_name)
        else:
            print("Layer {0}".format(index))
            for _, stack in layer:
                print("    {0}".format(stack.display_line()))
            print("")

@an_action(needs_stack=True, needs_credentials=True)
def deploy(collector, stack, **kwargs):
    """Deploy a particular stack"""
    Deployer().deploy_stack(stack, collector.configuration["stacks"])

@an_action(needs_stack=True, needs_credentials=True)
def publish_artifacts(collector, stack, **kwargs):
    """Build and publish an artifact"""
    Builder().publish_artifacts(stack)

@an_action(needs_stack=True, needs_credentials=True)
def clean_old_artifacts(collector, stack, **kwargs):
    """Cleanup old artifacts"""
    Builder().clean_old_artifacts(stack)

@an_action(needs_stack=True, needs_credentials=True)
def confirm_deployment(collector, stack, **kwargs):
    """Confirm deployment via SNS notification for each instance and/or url checks"""
    Deployer().confirm_deployment(stack)

@an_action(needs_artifact=True)
def print_variable(collector, stack, artifact, **kwargs):
    """Prints out a variable from the stack"""
    print(collector.configuration["bespin"].get_variable(artifact))

@an_action(needs_stack=True, needs_credentials=True)
def suspend_cloudformation_actions(collector, stack, **kwargs):
    """Suspends all schedule actions on a cloudformation stack"""
    Deployer().suspend_cloudformation_actions(stack)

@an_action(needs_stack=True, needs_credentials=True)
def resume_cloudformation_actions(collector, stack, **kwargs):
    """Resumes all schedule actions on a cloudformation stack"""
    Deployer().resume_cloudformation_actions(stack)

@an_action(needs_stack=True, needs_credentials=True)
def sanity_check(collector, stack, **kwargs):
    """Sanity check a stack and it's dependencies"""
    Builder().sanity_check(stack, collector.configuration["stacks"])
    log.info("All the stacks are sane!")

@an_action(needs_stack=True, needs_credentials=True)
def instances(collector, stack, artifact, **kwargs):
    """Find and ssh into instances"""
    if artifact is None:
        instance_ids = stack.ssh.find_instance_ids(stack)
        stack.ec2.display_instances(instance_ids, address=stack.ssh.address)
    else:
        # Have to convert instance ids into ip addresses
        if artifact.startswith("i-"):
            instance_ids = stack.ssh.find_instance_ids(stack)
            if artifact not in instance_ids:
                raise BadOption("Please specify either an IP Address or instance id that exists", instance_ids = instance_ids, got = artifact) 

            artifact = stack.ec2.ip_for_instance_id(artifact)

        # Artifact should be an ip address now !
        stack.ssh.ssh_into(artifact, collector.configuration["$@"])

@an_action()
def bastion(collector, **kwargs):
    """SSH into the bastion"""
    configuration = collector.configuration
    stack = list(configuration["stacks"].keys())[0]
    configuration["stacks"][stack].ssh.ssh_into_bastion(configuration["$@"])

@an_action(needs_credentials=True)
def execute(collector, **kwargs):
    """Exec a command using assumed credentials"""
    configuration = collector.configuration
    parts = shlex.split(configuration["$@"])
    configuration["bespin"].credentials.verify_creds()
    if not parts:
        suggestion = " ".join(sys.argv) + " -- /bin/command_to_run"
        msg = "No command was provided. Try something like:\n\t\t{0}".format(suggestion)
        raise BespinError(msg)
    os.execvpe(parts[0], parts, os.environ)

@an_action(needs_credentials=True, needs_stack=True)
def tail(collector, stack, **kwargs):
    """Tail the deployment of a stack"""
    stack.cloudformation.wait()

@an_action(needs_stack=True)
def params(collector, stack, **kwargs):
    """Print out the params"""
    stack.find_missing_env()
    print(stack.stack_name)
    print(json.dumps(stack.params_json_obj, indent=4))

@an_action(needs_stack=True, needs_credentials=True)
def outputs(collector, stack, artifact, **kwargs):
    """Print out the outputs"""
    outputs = stack.cloudformation.outputs
    if artifact not in (None, NotSpecified):
        if artifact not in outputs:
            raise BespinError("Couldn't find output", wanted=artifact, available=list(outputs.keys()))
        print(outputs[artifact])
    else:
        print(json.dumps(outputs, indent=4))

@an_action(needs_credentials=True)
def deploy_plan(collector, stack, artifact, **kwargs):
    """Deploy a predefined list of stacks in order"""
    plan = artifact if artifact else stack
    made = []
    checked = []
    deployer = Deployer()

    stacks = collector.configuration["stacks"]
    for stack in Plan.find_stacks(collector.configuration, stacks, plan):
        deployer.deploy_stack(stacks[stack], stacks, made=made, checked=checked)

@an_action(needs_credentials=True)
def sanity_check_plan(collector, stack, artifact, **kwargs):
    """sanity check a predefined list of stacks in order"""
    plan = artifact if artifact else stack
    checked = []
    builder = Builder()

    stacks = collector.configuration["stacks"]
    for stack in Plan.find_stacks(collector.configuration, stacks, plan):
        builder.sanity_check(stacks[stack], stacks, checked=checked)

@an_action(needs_stack=True, needs_credentials=True)
def command_on_instances(collector, stack, artifact, **kwargs):
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

    if collector.configuration["bespin"].dry_run:
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

@an_action(needs_stack=True, needs_credentials=True, needs_artifact=True)
def scale_instances(collector, stack, artifact, **kwargs):
    """Change the number of instances in the stack's auto_scaling_group"""
    if isinstance(artifact, int) or artifact.isdigit():
        artifact = int(artifact)
    else:
        raise BespinError("The number of instances must be an integer")

    if artifact > stack.scaling_options.instance_count_limit:
        raise BespinError("The instance_count_limit is smaller than the specified number of instances", limit=stack.scaling_options.instance_count_limit, wanted=artifact)

    group = stack.auto_scaling_group
    current_count = group.desired_capacity
    log.info("Changing the number of instances in the %s stack from %s to %s", stack.stack_name, current_count, artifact)

    if group.min_size > artifact:
        log.info("Changing min_size from %s to %s", group.min_size, artifact)
        group.min_size = artifact
    if group.max_size < artifact:
        log.info("Changing max_size from %s to %s", group.max_size, artifact)
        group.max_size = artifact

    if group.min_size < artifact:
        group.min_size = artifact
        if group.min_size > stack.scaling_options.highest_min:
            group.min_size = stack.scaling_options.highest_min

    group.desired_capacity = artifact
    group.update()

@an_action(needs_stack=True, needs_credentials=True)
def num_instances(collector, stack, **kwargs):
    """Count the number of running instances."""
    instance_ids = stack.ssh.find_instance_ids(stack)
    print(stack.ec2.num_alive_instances(instance_ids))

@an_action()
def become(collector, stack, artifact, **kwargs):
    """Print export statements for assuming an amazon iam role"""
    configuration = collector.configuration
    bespin = configuration['bespin']
    environment = bespin.environment
    region = configuration['environments'][environment].region

    if not environment:
        raise BadOption("Please specify an environment")

    if all(thing in ("", None, NotSpecified) for thing in (stack, artifact)):
        raise BespinError("Please specify your desired role as an artifact")

    if artifact:
        role = artifact
    else:
        role = stack

    credentials = Credentials(region, configuration["environments"][environment].account_id, role)
    credentials.verify_creds()

    print("export AWS_ACCESS_KEY_ID={0}".format(os.environ['AWS_ACCESS_KEY_ID']))
    print("export AWS_SECRET_ACCESS_KEY={0}".format(os.environ['AWS_SECRET_ACCESS_KEY']))
    print("export AWS_SECURITY_TOKEN={0}".format(os.environ['AWS_SECURITY_TOKEN']))
    print("export AWS_SESSION_TOKEN={0}".format(os.environ['AWS_SESSION_TOKEN']))

@an_action(needs_stack=True, needs_credentials=True)
def note_deployment_in_newrelic(collector, stack, **kwargs):
    """Note the deployment in newrelic"""
    if stack.newrelic is NotSpecified:
        raise BespinError("Please specify newrelic configuration for your stack")
    stack.newrelic.note_deployment()
    log.info("Great success!")

@an_action(needs_stack=True)
def downtime(collector, stack, method="downtime", **kwargs):
    """Downtime this stack in alerting systems"""
    if stack.downtimer_options is NotSpecified:
        raise BespinError("Nothing to downtime!")

    env = sb.listof(env_spec()).normalise(Meta({}, []), ["USER", "DURATION", "COMMENT"])
    missing = [e.env_name for e in env if e.missing]
    if missing:
        raise BespinError("Missing environment variables", missing=missing)
    provided_env = dict(e.pair for e in env)

    author = provided_env["USER"]
    comment = provided_env["COMMENT"]
    duration = provided_env["DURATION"]

    downtimer = Downtimer(stack.downtimer_options, dry_run=collector.configuration["bespin"].dry_run)
    for system, options in stack.alerting_systems.items():
        downtimer.register_system(system, options)

    getattr(downtimer, method)(duration, author, comment)

@an_action(needs_stack=True)
def undowntime(collector, **kwargs):
    """UnDowntime this stack in alerting systems"""
    kwargs["method"] = "undowntime"
    downtime(collector, **kwargs)

@an_action(needs_credentials=True)
def encrypt_password(collector, stack, artifact, **kwargs):
    """Convert plain text password into crypto text"""
    if artifact is None:
        key = stack
    else:
        key = artifact

    configuration = collector.configuration
    key = valid_password_key().normalise(Meta(configuration, []), key)
    password_options = configuration["passwords"][key]

    log.info("Generating a crypto_text for the %s password using %s as the KMS key id", key, password_options.KMSMasterKey)
    plain_text = getpass("Specify the password: ").encode('utf-8')

    res = configuration["bespin"].credentials.kms.encrypt(password_options.KMSMasterKey, plain_text, password_options.encryption_context, password_options.grant_tokens)
    log.info("Generated crypto text for %s", key)
    print(base64.b64encode(res["CiphertextBlob"]).decode('utf-8'))

def action_server_in_netscaler(collector, stack, artifact, server=NotSpecified, action=NotSpecified, **kwargs):
    if action is NotSpecified:
        raise ProgrammerError("Action needs to be specified")
    if action not in ("enable", "disable"):
        raise ProgrammerError("Action needs to be 'enable' or 'disable'")

    if server is NotSpecified:
        if artifact is None:
            server = stack
        else:
            server = artifact

    with collector.configuration["netscaler"] as netscaler:
        getattr(netscaler, "{0}_server".format(action))(server)

@an_action(needs_credentials=True)
def enable_server_in_netscaler(*args, **kwargs):
    """Disable a server in the netscaler"""
    kwargs["action"] = "enable"
    return action_server_in_netscaler(*args, **kwargs)

@an_action(needs_credentials=True)
def disable_server_in_netscaler(*args, **kwargs):
    """Enable a server in the netscaler"""
    kwargs["action"] = "disable"
    return action_server_in_netscaler(*args, **kwargs)

@an_action(needs_credentials=True, needs_stack=True)
def switch_dns_traffic_to(collector, stack, artifact, site=NotSpecified, **kwargs):
    """Switch dns traffic to some environment"""
    if stack.dns is NotSpecified:
        raise BespinError("No dns options are specified!")

    if site is NotSpecified and artifact not in ("", None, NotSpecified):
        site = artifact
    if site is NotSpecified or not site:
        site = None

    all_sites = stack.dns.sites()
    available = list(all_sites.keys())
    if site:
        if site not in available:
            raise BespinError("Have no dns options for specified site", available=available, wanted=site)
        sites = [site]
    else:
        sites = available
    sites = [all_sites[s] for s in sites]

    environment = collector.configuration["bespin"].environment
    errors = []
    for site in sorted(sites):
        if environment not in site.environments:
            errors.append(BespinError("Site doesn't have specified environment", site=site.name, wanted=environment, available=list(stack.environments.keys())))

        try:
            rtype, rdata = site.current_value
            if rtype != site.record_type:
                errors.append(BespinError("Site is a different record type!", recorded_as=rtype, wanted=site.record_type))

            log.info("%s is currently %s (%s)", site.domain, rdata, rtype)
        except BespinError as error:
            errors.append(error)
            continue

    if errors:
        raise BespinError("Prechecks failed", _errors=errors)

    log.info("Switching traffic to %s\tsites=%s", environment, [site.domain for site in sites])
    for site in sorted(sites):
        site.switch_to(collector.configuration["bespin"].environment, dry_run=collector.configuration["bespin"].dry_run)

@an_action(needs_stack=True, needs_credentials=True)
def sync_netscaler_config(collector, stack, **kwargs):
    """Sync netscaler configuration with the specified netscaler"""
    logging.captureWarnings(True)
    logging.getLogger("py.warnings").setLevel(logging.ERROR)
    configuration = collector.configuration

    if stack.netscaler is NotSpecified or stack.netscaler.configuration is NotSpecified:
        raise BespinError("Please configure {netscaler.configuration}")

    if stack.netscaler.syncable_environments is not NotSpecified:
        if configuration["environment"] not in stack.netscaler.syncable_environments:
            raise BespinError("Sorry, can only sync netscaler config for particular environments", wanted=configuration["environment"], available=list(stack.netscaler.syncable_environments))

    for_layers = []
    all_configuration = {}
    for vkey, value in stack.netscaler.configuration.items():
        for key, thing in value.items():
            if thing.environments is NotSpecified or configuration["environment"] in thing.environments:
                for_layers.append(thing.long_name)
                all_configuration[thing.long_name] = thing
                if vkey not in all_configuration:
                    all_configuration[vkey] = {}
                all_configuration[vkey][key] = thing

    layers = Layers(for_layers, all_stacks=all_configuration)
    layers.add_all_to_layers()

    stack.netscaler.syncing_configuration = True
    with stack.netscaler as netscaler:
        for layer in layers.layered:
            for _, thing in layer:
                netscaler.sync(all_configuration, configuration["environment"], thing)

@an_action(needs_stack=True, needs_credentials=True)
def wait_for_dns_switch(collector, stack, artifact, site=NotSpecified, **kwargs):
    """Periodically check dns until all our sites point to where they should be pointing to for specified environment"""

    if stack.dns is NotSpecified:
        raise BespinError("No dns options are specified!")

    if site is NotSpecified and artifact not in ("", None, NotSpecified):
        site = artifact
    if site is NotSpecified or not site:
        site = None

    all_sites = stack.dns.sites()
    available = list(all_sites.keys())
    if site:
        if site not in available:
            raise BespinError("Have no dns options for specified site", available=available, wanted=site)
        sites = [site]
    else:
        sites = available
    sites = [all_sites[s] for s in sites]

    environment = collector.configuration["bespin"].environment
    errors = []
    for site in sorted(sites):
        if environment not in site.environments:
            errors.append(BespinError("Site doesn't have specified environment", site=site.name, wanted=environment, available=list(stack.environments.keys())))

        try:
            rtype, rdata = site.current_value
            if rtype != site.record_type:
                errors.append(BespinError("Site is a different record type!", recorded_as=rtype, wanted=site.record_type))

            log.info("%s is currently %s (%s)", site.domain, rdata, rtype)
        except BespinError as error:
            errors.append(error)
            continue

    if errors:
        raise BespinError("Prechecks failed", _errors=errors)

    log.info("Waiting for traffic to switch to %s\tsites=%s", environment, [site.domain for site in sites])
    for _ in hp.until(timeout=600, step=5):
        if all(site.switched_to(environment) for site in sites):
            log.info("Finished switching!")
            break
        else:
            log.info("Waiting for sites to switch")

@an_action(needs_credentials=True, needs_stack=True)
def create_stackdriver_event(collector, stack, **kwargs):
    """Create an event in stackdriver"""
    env = get_from_env(["MESSAGE", "SENT_BY"])
    if stack.stackdriver is NotSpecified:
        raise BespinError("Please specify stackdriver options for your stack")
    stack.stackdriver.create_event(env["MESSAGE"], env['SENT_BY'])

# Make it so future use of @an_action doesn't result in more default tasks
info["is_default"] = False
