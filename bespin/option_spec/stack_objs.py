from bespin.errors import MissingOutput, BadOption, BadStack, BadJson, BespinError
from bespin.errors import StackDoesntExist, MissingSSHKey
from bespin.helpers import memoized_property
from bespin import helpers as hp

from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj
import logging
import shlex
import json
import stat
import six
import os
import re

log = logging.getLogger("bespin.option_spec.stack_objs")

class Stack(dictobj):
    fields = {
          "tags": """
              A dictionary specifying the tags to apply to the stack on creation"

              Note that a limitation of cloudformation is such that tags can only be
              applied to the template or changed at creation time.
          """
        , "name": "The name of this stack"
        , "key_name": "The original key of this stack in the configuration['stacks']"
        , "stack_name": """
            The name given to the deployed cloudformation stack

            Note that this may include environment variables as defined by the ``stack_name_env``
            option::

                stack_name: "rerun-{{RELEASE_VERSION}}"
                stack_name_env:
                    - RELEASE_VERSION
          """
        , "bespin": "The Bespin object"
        , "environment": "The name of the environment to deploy to"

        , "env": "A list of environment variables that are necessary for this deployment"
        , "build_env": "A list of environment variables that are necessary when building artifacts"
        , "stack_name_env": "A list of environment variables that are necessary for creating the stack name"

        , "build_first": "A list of stacks that should be built before this one is built"
        , "build_after": "A list of stacks that should be built after this one is buildt"
        , "ignore_deps": "Don't build any dependency stacks"
        , "suspend_actions": """
              Suspend Scheduled Actions for the stack before deploying, and resume Scheduled
              actions after finished deploying.

              This uses the ``auto_scaling_group_name`` attribute to determine what autoscaling group
              to suspend and resume
          """
        , "instance_count_limit": "The max number of instances the scale_instances action is allowed to scale to"
        , "skip_update_if_equivalent": "A list of two variable definitions. If they resolve to the same value, then don't deploy"
        , "artifact_retention_after_deployment": "Delete old artifacts after this deployment is done"

        , "vars": "A dictionary of variable definitions that may be referred to in other parts of the configuration"
        , "stack_json": "The path to a json file for the cloudformation stack definition"
        , "params_json": "The path to a json file for the parameters used by the cloudformation stack"
        , "params_yaml": "Either a dictionary of parameters to use in the stack, or path to a yaml file with the dictionary of parameters"
        , "auto_scaling_group_name": "The name of the auto scaling group used in the stack"

        , "ssh": "Options for ssh'ing into instances"
        , "artifacts": "Options for building artifacts used by the stack"

        , "command": "Used by the ``command_on_instances`` task as the command to run on the instances"
        , "confirm_deployment": "Options for confirming a deployment"
        }

    def __repr__(self):
        return "<Stack({0})>".format(self.name)

    def confirm_the_deployment(self, start=None):
        if self.confirm_deployment is not NotSpecified:
            self.find_missing_env()
            environment = dict(env.pair for env in self.env)
            self.confirm_deployment.confirm(self, environment, start)

    def physical_id_for(self, auto_scaling_group_id):
        return self.cloudformation.map_logical_to_physical_resource_id(auto_scaling_group_id)

    def dependencies(self, stacks):
        for key_name in self.build_first:
            yield key_name

        for value in self.vars.values():
            if hasattr(value, "stack") and not isinstance(value.stack, six.string_types):
                yield value.stack.key_name

    @property
    def stack_name(self):
        self.find_missing_stack_name_env()
        environment = dict([env.pair for env in self.stack_name_env])
        return self._stack_name.format(**environment)

    @stack_name.setter
    def stack_name(self, val):
        self._stack_name = val

    @property
    def build_after(self):
        for stack in self._build_after:
            if isinstance(stack, six.string_types):
                yield stack
            else:
                yield stack.key_name

    @build_after.setter
    def build_after(self, val):
        self._build_after = val

    @property
    def build_first(self):
        for stack in self._build_first:
            if isinstance(stack, six.string_types):
                yield stack
            else:
                yield stack.key_name

    @build_first.setter
    def build_first(self, val):
        self._build_first = val

    def display_line(self):
        return "Stack {0}".format(self.stack_name)

    def find_missing_env(self, key="env"):
        """Find any missing environment variables"""
        missing = [e.env_name for e in getattr(self, key) if e.missing]
        if missing:
            raise BadOption("Some environment variables aren't in the current environment", missing=missing)

    def find_missing_build_env(self):
        self.find_missing_env("build_env")

    def find_missing_stack_name_env(self):
        self.find_missing_env("stack_name_env")

    @memoized_property
    def cloudformation(self):
        return self.bespin.credentials.cloudformation(self.stack_name)

    @memoized_property
    def ec2(self):
        return self.bespin.credentials.ec2

    @memoized_property
    def sqs(self):
        return self.bespin.credentials.sqs

    @memoized_property
    def auto_scaling_group(self):
        asg_physical_id = self.cloudformation.map_logical_to_physical_resource_id(self.auto_scaling_group_name)
        return self.ec2.autoscale.get_all_groups(names=[asg_physical_id])[0]

    @memoized_property
    def s3(self):
        return self.bespin.credentials.s3

    @property
    def stack_json_obj(self):
        return self.stack_json

    @property
    def params_json_obj(self):
        if self.params_json is NotSpecified:
            params = json.dumps(self.params_json)
        else:
            params = json.dumps([{"ParameterKey": key, "ParameterValue": value} for key, value in self.params_yaml.items()])

        environment = dict([env.pair for env in self.env])

        if any(var.needs_credentials for var in self.vars.values()):
            self.bespin.set_credentials()

        for thing in (self.vars.items(), [env.pair for env in self.env]):
            for var, value in thing:
                key = "XXX_{0}_XXX".format(var.upper())
                if key in params:
                    if not isinstance(value, six.string_types):
                        value = value.resolve()
                    params = params.replace(key, value.format(**environment))

        try:
            return json.loads(params)
        except ValueError as error:
            raise BadJson("Couldn't parse the parameters", filename=self.params_json, stack=self.key_name, error=error)

    def create_or_update(self):
        """Create or update the stack, return True if the stack actually changed"""
        log.info("Creating or updating the stack (%s)", self.stack_name)
        status = self.cloudformation.wait(may_not_exist=True)

        if not status.exists:
            log.info("No existing stack, making one now")
            if self.bespin.dry_run:
                log.info("DRYRUN: Would create stack")
            else:
                return self.cloudformation.create(self.stack_json_obj, self.params_json_obj, self.tags.as_dict() or None)
        elif status.complete:
            log.info("Found existing stack, doing an update")
            if self.bespin.dry_run:
                log.info("DRYRUN: Would update stack")
            else:
                return self.cloudformation.update(self.stack_json_obj, self.params_json_obj)
        else:
            raise BadStack("Stack could not be updated", name=self.stack_name, status=status.name)

        return False

    def sanity_check(self):
        self.find_missing_env()
        if all(isinstance(item, six.string_types) for item in (self.params_json, self.params_yaml)):
            raise BadStack("Need either params_json or params_yaml", looking_in=[self.params_json, self.params_yaml])
        if not any(isinstance(item, six.string_types) for item in (self.params_json, self.params_yaml)):
            raise BadStack("Please don't have both params_json and params_yaml")
        matches = re.findall("XXX_[A-Z_]+_XXX", json.dumps(self.params_json_obj))
        if matches:
            raise BadStack("Found placeholders in the generated params file", stack=self.name, found=matches)
        if self.cloudformation.status.failed:
            raise BadStack("Stack is in a failed state, this means it probably has to be deleted first....", stack=self.stack_name)

        with hp.a_temp_file() as fle:
            json.dump(self.stack_json_obj, open(fle.name, "w"))
            self.cloudformation.validate_template(fle.name)

class StaticVariable(dictobj):
    fields = ["value", ("needs_credentials", False)]

    def resolve(self):
        return self.value

class DynamicVariable(dictobj):
    fields = ["stack", "output", ("bespin", None), ("needs_credentials", True)]

    def resolve(self):
        if isinstance(self.stack, six.string_types):
            cloudformation = self.bespin.credentials.cloudformation(self.stack)
            cloudformation.wait()
            outputs = cloudformation.outputs
        else:
            outputs = self.stack.cloudformation.outputs

        if self.output not in outputs:
            raise MissingOutput(wanted=self.output, available=outputs.keys())

        return outputs[self.output]

class Environment(dictobj):
    """A single environment variable, and it's default or set value"""
    fields = ["env_name", ("default_val", None), ("set_val", None)]

    @property
    def missing(self):
        return self.default_val is None and self.set_val is None and self.env_name not in os.environ

    @property
    def pair(self):
        """Get the name and value for this environment variable"""
        if self.set_val is not None:
            return self.env_name, self.set_val
        elif self.default_val is not None:
            return self.env_name, os.environ.get(self.env_name, self.default_val)
        else:
            return self.env_name, os.environ[self.env_name]

class Skipper(dictobj):
    fields = ["var1", "var2"]

    def resolve(self):
        try:
            v1 = self.var1().resolve()
        except StackDoesntExist:
            return False

        try:
            v2 = self.var2().resolve()
        except StackDoesntExist:
            return False

        return v1 and v2 and v1 == v2

class SSH(dictobj):
    fields = {
          "user": "The user to ssh into the instances as"
        , "bastion": "The bastion jumpbox to use to get to the instances"
        , "address": "The address to use to get into the single instance if ``instance`` is specified"
        , "instance": "The Logical id of the instance in the template to ssh into"
        , "auto_scaling_group_name": "The logical id of the auto scaling group that has the instances of interest"

        , "bastion_key_path": "The location on disk of the bastion ssh key"
        , "instance_key_path": "The location on disk of the instance ssh key"
        , "bastion_key_location": "The place where the bastion key may be downloaded from"
        , "instance_key_location": "The place where the instance key may be downloaded from"
        }

    def find_instance_ids(self, stack):
        if self.auto_scaling_group_name is not NotSpecified:
            instance = None
            asg_physical_id = stack.cloudformation.map_logical_to_physical_resource_id(self.auto_scaling_group_name)
        elif self.instance is not NotSpecified:
            instance = stack.cloudformation.map_logical_to_physical_resource_id(self.instance)
            asg_physical_id = None
        else:
            raise BespinError("Please specify either ssh.instance or ssh.auto_scaling_group_name", stack=stack)

        log.info("Finding instances")
        instance_ids = []
        if asg_physical_id:
            instance_ids = stack.ec2.instance_ids_in_autoscaling_group(asg_physical_id)
        elif instance:
            instance_ids = [instance]

        return instance_ids

    def find_ips(self, stack):
        if self.address is not NotSpecified:
            return [self.address]
        else:
            instance_ids = self.find_instance_ids(stack)
            return stack.ec2.ips_for_instance_ids(instance_ids)

    def proxy_options(self, bastion_key_path):
        if self.bastion is not NotSpecified:
            return '-o ProxyCommand="ssh {0}@{1} -W %h:%p -i {2} -o IdentitiesOnly=true"'.format(self.user, self.bastion, bastion_key_path)
        else:
            return ""

    def ssh_into_bastion(self, extra_args):
        self.chmod_bastion_key_path()
        command = "ssh {0}@{1} -i {2} -o IdentitiesOnly=true".format(self.user, self.bastion, self.bastion_key_path)
        parts = shlex.split(command)
        os.execvp(parts[0], parts)

    def ssh_into(self, ip_address, extra_args):
        bastion_key_path, instance_key_path = self.chmod_keys()
        proxy = self.proxy_options(bastion_key_path)

        if proxy:
            log.info("Logging into %s via %s", ip_address, self.bastion)
        else:
            log.info("Logging into %s", ip_address)

        command = "ssh -o ForwardAgent=false -o IdentitiesOnly=true {0} -i {1} {2}@{3} {4}".format(proxy, instance_key_path, self.user, ip_address, extra_args)
        parts = shlex.split(command)
        log.debug("Running %s", command)
        os.execvp(parts[0], parts)

    def chmod_keys(self):
        error = False
        bastion_key_path = None
        if self.bastion is not NotSpecified:
            try:
                bastion_key_path = self.chmod_bastion_key_path()
            except MissingSSHKey:
                error = True

        try:
            instance_key_path = self.chmod_instance_key_path()
        except MissingSSHKey:
            error = True

        if error:
            raise BespinError("Couldn't find ssh keys")

        return bastion_key_path, instance_key_path

    def chmod_instance_key_path(self):
        if not os.path.exists(self.instance_key_path):
            log.error("Didn't find a instance key, please download the key")
            print("Instance key can be found at {0}".format(self.instance_key_location))
            print("Download it to {0}".format(self.instance_key_path))
            raise MissingSSHKey()

        os.chmod(self.instance_key_path, 0)
        os.chmod(self.instance_key_path, stat.S_IRUSR)
        return self.instance_key_path

    def chmod_bastion_key_path(self):
        if not os.path.exists(self.bastion_key_path):
            log.error("Didn't find a bastion key, please download the key")
            print("Bastion key can be found at {0}".format(self.bastion_key_location))
            print("Download it to {0}".format(self.bastion_key_path))
            raise MissingSSHKey(looking_for="bastion")

        os.chmod(self.bastion_key_path, 0)
        os.chmod(self.bastion_key_path, stat.S_IRUSR)
        return self.bastion_key_path

class S3Address(dictobj):
    fields = ["bucket", "key", "timeout"]

