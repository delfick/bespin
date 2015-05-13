from bespin.errors import BadDeployment, BadStack, BadOption
from bespin import helpers as hp

from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj
import requests
import fnmatch
import logging

log = logging.getLogger("bespin.option_spec.deployment")

class UrlChecker(dictobj):
    fields = {
          "expect": "The value we expect for a successful deployment"
        , "endpoint": "The domain of the url to hit"
        , "check_url": "The path of the url to hit"
        , "timeout_after": "Stop waiting after this many seconds"
        }

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
    fields = {
          "version_message": "The expected version that indicates successful deployment"
        , "deployment_queue": "The sqs queue to check for messages"
        , ("timeout", 300): "Stop waiting after this amount of time"
        }

    def wait(self, instances, environment, sqs):
        version_message = self.version_message.format(**environment)

        failed = []
        success = []
        attempt = 0

        log.info("Checking sqs for %s", version_message)
        log.info("Checking for message for instances [%s]", ",".join(instances))
        for _ in hp.until(timeout=self.timeout, step=5, action="Checking for valid deployment actions"):
            messages = sqs.get_all_deployment_messages(self.deployment_queue)

            # Look for success and failure in the messages
            for message in messages:
                log.info("Message received for instance %s with content [%s]", message.instance_id, message.output)

                # Ignore the messages for instances outside this deployment
                if message.instance_id in instances:
                    if fnmatch.fnmatch(message.output, version_message):
                        log.info("Deployed instance %s", message.instance_id)
                        success.append(message.instance_id)
                    else:
                        log.info("Failed to deploy instance %s", message.instance_id)
                        log.info("Failure Message: %s", message.output)
                        failed.append(message.instance_id)

            # Stop trying if we have all the instances
            if set(failed + success) == set(instances):
                break

            # Record the iteration of checking for a valid deployment
            attempt += 1
            log.info("Completed attempt %s of checking for a valid deployment state", attempt)

        if success:
            log.info("Succeeded to deploy %s", success)
        if failed:
            log.error("Failed to deploy %s", failed)
            raise BadDeployment(failed=failed)

        if not success and not failed:
            log.error("Failed to receive any messages")
            raise BadDeployment("Failed to receive any messages")

        log.info("All instances have been confirmed to be deployed with version_message [%s]!", version_message)

class ConfirmDeployment(dictobj):
    fields = {
          "deploys_s3_path": "A list of s3 paths that we expect to be created as part of the deployment"
        , "zero_instances_is_ok": "Don't do deployment confirmation if the scaling group has no instances"
        , "auto_scaling_group_name": "The name of the auto scaling group that has the instances to be checked"
        , "url_checker": "Check an endpoint on our instances for a particular version message"
        , "sns_confirmation": "Check an sqs queue for messages our Running instances produced"
        }

    def instances(self, stack):
        auto_scaling_group_name = self.auto_scaling_group_name
        asg_physical_id = stack.cloudformation.map_logical_to_physical_resource_id(auto_scaling_group_name)
        return stack.ec2.get_instances_in_asg_by_lifecycle_state(asg_physical_id, lifecycle_state="InService")

    def confirm(self, stack, environment, start=None):
        instances = []
        if self.auto_scaling_group_name is not NotSpecified:
            instances = self.instances(stack)

            if len(instances) is 0:
                if self.zero_instances_is_ok:
                    log.info("No instances to check, but config says that's ok!")
                    return
                else:
                    raise BadDeployment("No instances are InService in the auto scaling group!", stack=stack.name, auto_scaling_group_name=self.auto_scaling_group_name)
        else:
            if any(item is not NotSpecified for item in (self.sns_confirmation, self.url_checker)):
                raise BadOption("Auto_scaling_group_name must be specified if sns_confirmation or url_checker are specified")

        for checker in (self.check_sns, self.check_url, self.check_deployed_s3_paths):
            checker(stack, instances, environment, start)

    def check_sns(self, stack, instances, environment, start=None):
        if self.sns_confirmation is not NotSpecified:
            self.sns_confirmation.wait(instances, environment, stack.sqs)

    def check_url(self, stack, instances, environment, start=None):
        if self.url_checker is not NotSpecified:
            self.url_checker.wait(environment)

    def check_deployed_s3_paths(self, stack, instances, environment, start=None):
        if self.deploys_s3_path is not NotSpecified:
            for path in self.deploys_s3_path:
                stack.s3.wait_for(path.bucket.format(**environment), path.key.format(**environment), path.timeout, start=start)

