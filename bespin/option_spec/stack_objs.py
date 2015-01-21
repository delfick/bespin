from bespin.errors import MissingOutput, BadOption, BadStack, BadJson, BespinError
from bespin.errors import StackDoesntExist, BadDeployment, MissingVariable
from bespin.helpers import memoized_property
from input_algorithms.meta import Meta
from bespin import helpers as hp

from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj
import requests
import fnmatch
import logging
import shlex
import json
import stat
import six
import os

log = logging.getLogger("bespin.option_spec.stack_objs")

class Stack(dictobj):
    fields = [
          "bespin", "name", "key_name", "environment", "stack_json", "params_json"
        , "vars", "stack_name", "env", "build_after", "ignore_deps", "artifacts"
        , "skip_update_if_equivalent", "tags", "sns_confirmation", "ssh", "build_env"
        , "artifact_retention_after_deployment", "suspend_actions", "url_checker"
        ]

    def __repr__(self):
        return "<Stack({0})>".format(self.name)

    def physical_id_for(self, autoscaling_group_id):
        return self.cloudformation.map_logical_to_physical_resource_id(autoscaling_group_id)

    def check_url(self):
        environment = dict(env.pair for env in self.env)
        if self.url_checker is not NotSpecified:
            self.url_checker.wait(environment)

    def check_sns(self):
        environment = dict(env.pair for env in self.env)
        if self.sns_confirmation is not NotSpecified:
            self.sns_confirmation.wait(environment, self.ec2, self.sqs, self.cloudformation)

    def dependencies(self, stacks):
        for value in self.vars.values():
            if hasattr(value, "stack") and not isinstance(value.stack, six.string_types):
                yield value.stack.key_name

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

    def display_line(self):
        return "Stack {0}".format(self.stack_name)

    def get_variable(self, artifact):
        try:
            return self.vars[artifact].resolve()
        except KeyError:
            raise MissingVariable(wanted=artifact, available=list(self.vars.keys()))

    def find_missing_env(self, key="env"):
        """Find any missing environment variables"""
        missing = [e.env_name for e in getattr(self, key) if e.missing]
        if missing:
            raise BadOption("Some environment variables aren't in the current environment", missing=missing)

    def find_missing_build_env(self):
        self.artifacts.find_missing_env("build_env")

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
    def s3(self):
        return self.bespin.credentials.s3

    @property
    def params_json_obj(self):
        with open(self.params_json) as fle:
            params = fle.read()

        for thing in (self.vars.items(), [env.pair for env in self.env]):
            for var, value in thing:
                key = "XXX_{0}_XXX".format(var.upper())
                if key in params:
                    if not isinstance(value, six.string_types):
                        value = value.resolve()
                    params = params.replace(key, value)

        try:
            return json.loads(params)
        except ValueError as error:
            raise BadJson("Couldn't parse the parameters", filename=self.params_json, stack=self.key_name, error=error)

    @hp.memoized_property
    def stack_json_obj(self):
        try:
            return json.load(open(self.stack_json))
        except ValueError as error:
            raise BadJson("Couldn't parse the stack", filename=self.stack_json, stack=self.key_name, error=error)

    def create_or_update(self):
        log.info("Creating or updating the stack (%s)", self.stack_name)
        status = self.cloudformation.wait()

        if not status.exists:
            log.info("No existing stack, making one now")
            if self.bespin.dry_run:
                log.info("DRYRUN: Would create stack")
            else:
                self.cloudformation.create(self.stack_json_obj, self.params_json_obj, self.tags.as_dict() or None)
        elif status.complete:
            log.info("Found existing stack, doing an update")
            if self.bespin.dry_run:
                log.info("DRYRUN: Would update stack")
            else:
                self.cloudformation.update(self.stack_json_obj, self.params_json_obj)
        else:
            raise BadStack("Stack could not be updated", name=self.stack_name, status=status.name)

    def sanity_check(self):
        from bespin.option_spec import stack_specs
        self.find_missing_env()
        self.find_missing_artifact_env()
        stack_specs.stack_json_spec().normalise(Meta({}, []), self.stack_json_obj)
        if os.path.exists(self.params_json):
            stack_specs.params_json_spec().normalise(Meta({}, []), json.load(open(self.params_json)))
        if self.cloudformation.status.failed:
            raise BadStack("Stack is in a failed state, this means it probably has to be deleted first....", stack=self.stack_name)
        self.cloudformation.validate_template(self.stack_json)

class StaticVariable(dictobj):
    fields = ["value"]

    def resolve(self):
        return self.value

class DynamicVariable(dictobj):
    fields = ["stack", "output", ("bespin", None)]

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
    fields = [
          "user", "bastion", "bastion_key_location"
        , "instance_key_location", "autoscaling_group_name"
        , "instance_key_path", "bastion_key_path"
        ]

    def ssh_into_bastion(self, extra_args):
        if not os.path.exists(self.bastion_key_path):
            log.error("Didn't find a bastion key, please download the key")
            print("Bastion key can be found at {0}".format(self.bastion_key_location))
            print("Download it to {0}".format(self.bastion_key_path))
            raise BespinError("Couldn't find an ssh key for the bastion")

        os.chmod(self.bastion_key_path, 0)
        os.chmod(self.bastion_key_path, stat.S_IRUSR)

        command = "ssh {0}@{1} -i {2} -o IdentitiesOnly=true".format(self.user, self.bastion, self.bastion_key_path)
        parts = shlex.split(command)
        os.execvp(parts[0], parts)

    def ssh_into(self, ip_address, extra_args):
        proxy = ""
        error = False
        if self.bastion is not NotSpecified:
            log.info("Logging into %s via %s", ip_address, self.bastion)
            if not os.path.exists(self.bastion_key_path):
                log.error("Didn't find a bastion key, please download the key")
                print("Bastion key can be found at {0}".format(self.bastion_key_location))
                print("Download it to {0}".format(self.bastion_key_path))
                error = True
            proxy = '-o ProxyCommand="ssh {0}@{1} -W %h:%p -i {2} -o IdentitiesOnly=true"'.format(self.user, self.bastion, self.bastion_key_path)
        else:
            log.info("Logging into %s", ip_address)

        if not os.path.exists(self.instance_key_path):
            log.error("Didn't find a instance key, please download the key")
            print("Instance key can be found at {0}".format(self.instance_key_location))
            print("Download it to {0}".format(self.instance_key_path))
            error = True

        if error:
            raise BespinError("Couldn't find ssh keys")

        os.chmod(self.instance_key_path, 0)
        os.chmod(self.instance_key_path, stat.S_IRUSR)
        os.chmod(self.bastion_key_path, 0)
        os.chmod(self.bastion_key_path, stat.S_IRUSR)

        command = "ssh -o ForwardAgent=false -o IdentitiesOnly=true {0} -i {1} {2}@{3} {4}".format(proxy, self.instance_key_path, self.user, ip_address, extra_args)
        parts = shlex.split(command)
        log.debug("Running %s", command)
        os.execvp(parts[0], parts)

class UrlChecker(dictobj):
    fields = ["check_url", "endpoint", "expect", "timeout_after"]

    def wait(self, environment):
        endpoint = self.endpoint().resolve()
        while endpoint.endswith("/"):
            endpoint = endpoint[:-1]
        while endpoint.endswith("."):
            endpoint = endpoint[:-1]

        while self.check_url.startswith("/"):
            self.check_url = self.check_url[1:]

        url = endpoint + '/' + self.check_url
        expected = self.expect.format(**environment)

        log.info("Asking server for version till we match %s", expected)
        for _ in hp.until(self.timeout_after, step=15):
            log.info("Asking %s", url)
            try:
                result = requests.get(url).text
            except requests.exceptions.ConnectionError as error:
                log.warning("Failed to ask server\terror=%s", error)
            else:
                log.info("\tgot back %s", result)
                if fnmatch.fnmatch(result, expected):
                    log.info("Deployment successful!")
                    return

        raise BadStack("Timedout waiting for the app to give back the correct version")

class SNSConfirmation(dictobj):
    fields = ["version_message", "env", "deployment_queue", "autoscaling_group_id"]

    def wait(self, environment, ec2, sqs, cloudformation):
        autoscaling_group_id = self.autoscaling_group_id
        asg_physical_id = cloudformation.map_logical_to_physical_resource_id(autoscaling_group_id)
        instances_to_check = ec2.get_instances_in_asg_by_lifecycle_state(asg_physical_id, lifecycle_state="InService")

        version_message = self.version_message.format(**environment)

        failed = []
        success = []
        attempt = 0

        for _ in hp.until(action="Checking for valid deployment actions"):
            messages = sqs.get_all_deployment_messages(self.deployment_queue)

            # Look for success and failure in the messages
            for message in messages:
                log.info("Message received %s", message['output'])

                # Ignore the messages for instances outside this deployment
                if message['instance_id'] in instances_to_check:
                    if fnmatch.fnmatch(message['output'], version_message):
                        log.info("Deployed instance %s", message['instance_id'])
                        success.append(message['instance_id'])
                    else:
                        log.info("Failed to deploy instance %s", message['instance_id'])
                        log.info("Failure Message: %s", message['output'])
                        failed.append(message['instance_id'])

            # Stop trying if we have all the instances
            if set(failed + success) == set(instances_to_check):
                break

            # Record the iteration of checking for a valid deployment
            attempt += 1
            log.info("Completed attempt %s of checking for a valid deployment state", attempt)

        if success:
            log.info("Succeeded to deploy %s", success)
        if failed:
            log.info("Failed to deploy %s", failed)
            raise BadDeployment(failed=failed)

        log.info("All instances have been confirmed to be deployed with version_message [%s]!", version_message)

