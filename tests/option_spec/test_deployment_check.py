# coding: spec

from bespin.option_spec.deployment_check import SNSConfirmation
from bespin.errors import BadStack, BadDeployment, BadOption
from bespin.option_spec.bespin_specs import BespinSpec
from bespin.amazon.sqs import Message

from tests.helpers import BespinCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms.spec_base import NotSpecified
from input_algorithms.meta import Meta
import mock

describe BespinCase, "UrlChecker":
    def make_checker(self, **kwargs):
        return BespinSpec().url_checker_spec.normalise(Meta({}, []), kwargs)

    describe "wait":
        it "concatenates endpoint and check_url to get the final url to check":
            called = []
            def get(url):
                called.append(url)
                return mock.Mock(name="response", text="blah-1.2")
            requests_get = mock.Mock(name="get", side_effect=get)

            with mock.patch("requests.get", requests_get):
                checker = self.make_checker(expect="blah*", endpoint="http://somewhere.com/", check_url="/diagnostic/version", timeout_after=20)
                checker.wait({})

            self.assertEqual(called, ["http://somewhere.com/diagnostic/version"])

        it "retries every 15 seconds":
            called = []
            sleeps = []
            info = {"index": -1, "responses": ["tree", "derp", "meh", "blah-1.2"]}
            def get(url):
                called.append(url)
                info["index"] += 1
                return mock.Mock(name="response", text=info["responses"][info["index"]])
            requests_get = mock.Mock(name="get", side_effect=get)

            sleep = mock.Mock(name='sleep', side_effect=lambda amount: sleeps.append(amount))

            with mock.patch("time.sleep", sleep):
                with mock.patch("requests.get", requests_get):
                    checker = self.make_checker(expect="blah*", endpoint="http://somewhere.com/", check_url="/diagnostic/version", timeout_after=20)
                    checker.wait({})

            self.assertEqual(called, ["http://somewhere.com/diagnostic/version"] * 4)
            self.assertEqual(sleeps, [15] * 3)

        it "raises BadStack if it timesout":
            requests_get = mock.Mock(name="get", side_effect=lambda url: mock.Mock(name="response", text="whatever"))
            sleep = mock.Mock(name='sleep', side_effect=lambda amount: None)

            with self.fuzzyAssertRaisesError(BadStack, "Timedout waiting for the app to give back the correct version"):
                with mock.patch("time.sleep", sleep):
                    with mock.patch("requests.get", requests_get):
                        checker = self.make_checker(expect="blah*", endpoint="http://somewhere.com/", check_url="/diagnostic/version", timeout_after=0)
                        checker.wait({})

describe BespinCase, "SNSConfirmation":
    describe "wait":
        it "succeeds if we get messages for all the instances with the correct version":
            message1 = Message.decode("success:i-1:blah-9")
            message2 = Message.decode("success:i-2:blah-9")
            message3 = Message.decode("success:i-3:blah-9")
            message4 = Message.decode("success:i-4:blah-9")
            messages = [message1, message2, message3, message4]

            sqs = mock.Mock(name="sqs")
            sqs.get_all_deployment_messages.return_value = messages
            queue = mock.Mock(name="queue")
            queue.format.return_value = queue

            confirmation = SNSConfirmation(version_message="{VAR}*", deployment_queue=queue)
            confirmation.wait(["i-1", "i-2", "i-3", "i-4"], {"VAR": "blah"}, sqs)

            sqs.get_all_deployment_messages.assert_called_once_with(queue)

        it "fails if any of the instances has the incorrect version":
            message1 = Message.decode("success:i-1:blah-9")
            message2 = Message.decode("success:i-2:meh-9")
            message3 = Message.decode("success:i-3:blah-9")
            message4 = Message.decode("success:i-4:blah-9")
            messages = [message1, message2, message3, message4]

            sqs = mock.Mock(name="sqs")
            sqs.get_all_deployment_messages.return_value = messages
            queue = mock.Mock(name="queue")
            queue.format.return_value = queue

            confirmation = SNSConfirmation(version_message="{VAR}*", deployment_queue=queue)
            with self.fuzzyAssertRaisesError(BadDeployment, failed=["i-2"]):
                confirmation.wait(["i-1", "i-2", "i-3", "i-4"], {"VAR": "blah"}, sqs)

            sqs.get_all_deployment_messages.assert_called_once_with(queue)

        it "ignores messages with unrelated instance ids":
            message1 = Message.decode("success:i-1:blah-9")
            message2 = Message.decode("success:i-5:meh-9")
            message3 = Message.decode("success:i-3:blah-9")
            message4 = Message.decode("success:i-4:blah-9")
            message5 = Message.decode("success:i-2:blah-9")
            message6 = Message.decode("failure:i-6:blah-9")
            messages = [message1, message2, message3, message4, message5, message6]

            sqs = mock.Mock(name="sqs")
            sqs.get_all_deployment_messages.return_value = messages
            queue = mock.Mock(name="queue")
            queue.format.return_value = queue

            confirmation = SNSConfirmation(version_message="{VAR}*", deployment_queue=queue)
            confirmation.wait(["i-1", "i-2", "i-3", "i-4"], {"VAR": "blah"}, sqs)

            sqs.get_all_deployment_messages.assert_called_once_with(queue)

        it "tries get_all_deployment_messages until we have all the instances":
            called = []
            sleeps = []

            message1 = Message.decode("success:i-1:blah-9")
            message2 = Message.decode("success:i-5:meh-9")
            message3 = Message.decode("success:i-3:blah-9")
            message4 = Message.decode("success:i-4:blah-9")
            message5 = Message.decode("success:i-2:blah-9")
            message6 = Message.decode("failure:i-6:blah-9")

            messages1 = [message1]
            messages2 = [message2, message3]
            messages3 = [message4]
            messages4 = [message5, message6]
            info = {"index": -1, "responses": [[], messages1, messages2, messages3, messages4]}

            sqs = mock.Mock(name="sqs")
            def get_all_deployment_messages(queue):
                called.append(queue)
                info["index"] += 1
                return info["responses"][info["index"]]
            sqs.get_all_deployment_messages.side_effect = get_all_deployment_messages
            queue = mock.Mock(name="queue")
            queue.format.return_value = queue
            sleep = mock.Mock(name="sleep", side_effect=lambda amount: sleeps.append(amount))

            with mock.patch("time.sleep", sleep):
                confirmation = SNSConfirmation(version_message="{VAR}*", deployment_queue=queue)
                confirmation.wait(["i-1", "i-2", "i-3", "i-4"], {"VAR": "blah"}, sqs)

            self.assertEqual(called, [queue] * 5)
            self.assertEqual(sleeps, [5] * 4)

        it "fails if it gets no messages before timeout":
            sqs = mock.Mock(name="sqs")
            sqs.get_all_deployment_messages.return_value = []
            queue = mock.Mock(name="queue")
            queue.format.return_value = queue
            sleep = mock.Mock(name="sleep")

            with self.fuzzyAssertRaisesError(BadDeployment, "Failed to receive any messages"):
                with mock.patch("time.sleep", sleep):
                    confirmation = SNSConfirmation(version_message="{VAR}*", deployment_queue=queue, timeout=0)
                    confirmation.wait(["i-1", "i-2", "i-3", "i-4"], {"VAR": "blah"}, sqs)

describe BespinCase, "ConfirmDeployment":
    before_each:
        self.start = mock.Mock(name="start")
        self.stack = mock.Mock(name="stack")
        self.instances = mock.Mock(name="instances")
        self.environment = mock.Mock(name="environment")

        self.sqs = mock.Mock(name="sqs")
        self.stack.sqs = self.sqs

        self.s3 = mock.Mock(name="s3")
        self.stack.s3 = self.s3

    describe "check_sns":
        it "does nothing if sns_confirmation is NotSpecified":
            confirmation = BespinSpec().confirm_deployment_spec.normalise(Meta({}, []), {})
            assert confirmation.sns_confirmation is NotSpecified
            confirmation.check_sns(stack=None, instances=None, environment=None)
            assert True

        it "calls wait on sns_confirmation if it exists":
            confirmation = BespinSpec().confirm_deployment_spec.normalise(Meta({}, []), {})
            sns_confirmation = mock.Mock(name="sns_confirmation")
            confirmation.sns_confirmation = sns_confirmation
            confirmation.check_sns(stack=self.stack, instances=self.instances, environment=self.environment, start=self.start)
            sns_confirmation.wait.assert_called_once_with(self.instances, self.environment, self.sqs)

    describe "check_url":
        it "does nothing if url_checker is NotSpecified":
            confirmation = BespinSpec().confirm_deployment_spec.normalise(Meta({}, []), {})
            assert confirmation.url_checker is NotSpecified
            confirmation.check_url(stack=None, instances=None, environment=None)
            assert True

        it "calls wait on url_checker if it exists":
            confirmation = BespinSpec().confirm_deployment_spec.normalise(Meta({}, []), {})
            url_checker = mock.Mock(name="url_checker")
            confirmation.url_checker = url_checker
            confirmation.check_url(stack=self.stack, instances=self.instances, environment=self.environment, start=self.start)
            url_checker.wait.assert_called_once_with(self.environment)

    describe "check_deployed_s3_paths":
        it "does nothing if there are no deploys_s3_path specified":
            confirmation = BespinSpec().confirm_deployment_spec.normalise(Meta({}, []), {})
            assert confirmation.deploys_s3_path is NotSpecified
            confirmation.check_deployed_s3_paths(stack=None, instances=None, environment=None)
            assert True

        it "asks stack.s3 to wait for each defined path":
            confirmation = BespinSpec().confirm_deployment_spec.normalise(Meta({}, []), {"deploys_s3_path":["s3://one/{{VAR}}/three.sql", "s3://two/four/five.tar.gz"]})
            confirmation.check_deployed_s3_paths(stack=self.stack, instances=self.instances, environment={"VAR":"meh"}, start=self.start)
            self.assertEqual(self.s3.wait_for.mock_calls,
                [ mock.call("one", "/meh/three.sql", 600, start=self.start)
                , mock.call("two", "/four/five.tar.gz", 600, start=self.start)
                ]
            )

    describe "confirm":
        it "complains if auto_scaling_group_name is not specified when it's needed":
            sns_options = {"version_message": "whatever", "deployment_queue": "queue"}
            url_options = {"check_url": "/blah", "expect": "whatever", "endpoint": "http://somewhere"}
            for options in [{"sns_confirmation":sns_options}, {"url_checker":url_options}, {"url_checker": url_options, "sns_confirmation": sns_options}]:
                with self.fuzzyAssertRaisesError(BadOption, "Auto_scaling_group_name must be specified if sns_confirmation or url_checker are specified"):
                    confirmation = BespinSpec().confirm_deployment_spec.normalise(Meta({}, []), options)
                    confirmation.confirm(self.stack, self.environment)

        it "doesn't need an auto scaling group if we are only checking deploys_s3_path":
            confirmation = BespinSpec().confirm_deployment_spec.normalise(Meta({}, []), {"deploys_s3_path":["s3://path/blah.sql"]})
            check_deployed_s3_paths = mock.Mock(name="check_deployed_s3_paths")
            with mock.patch("bespin.option_spec.deployment_check.ConfirmDeployment.check_deployed_s3_paths", check_deployed_s3_paths):
                confirmation.confirm(self.stack, self.environment, start=self.start)
            check_deployed_s3_paths.assert_called_once_with(self.stack, [], self.environment, self.start)

        it "finds the instances and passes them into the checkers":
            instances = mock.MagicMock(name="instances", __len__=lambda *args: 2)
            check_sns = mock.Mock(name="check_sns")
            check_url = mock.Mock(name="check_url")
            check_deployed_s3_paths = mock.Mock(name="check_deployed_s3_paths")

            confirmation = BespinSpec().confirm_deployment_spec.normalise(Meta({}, []), {"auto_scaling_group_name":"whatever"})
            with mock.patch.multiple(confirmation, instances=(lambda *args: instances), check_sns=check_sns, check_url=check_url, check_deployed_s3_paths=check_deployed_s3_paths):
                confirmation.confirm(self.stack, self.environment, start=self.start)

            check_sns.assert_called_once_with(self.stack, instances, self.environment, self.start)
            check_url.assert_called_once_with(self.stack, instances, self.environment, self.start)
            check_deployed_s3_paths.assert_called_once_with(self.stack, instances, self.environment, self.start)

        it "does nothing if there are no instances and zero_instances_is_ok":
            instances = mock.MagicMock(name="instances", __len__=lambda *args: 0)
            check_sns = mock.Mock(name="check_sns")
            check_url = mock.Mock(name="check_url")
            check_deployed_s3_paths = mock.Mock(name="check_deployed_s3_paths")

            confirmation = BespinSpec().confirm_deployment_spec.normalise(Meta({}, []), {"auto_scaling_group_name":"whatever", "zero_instances_is_ok": True})
            with mock.patch.multiple(confirmation, instances=(lambda *args: instances), check_sns=check_sns, check_url=check_url, check_deployed_s3_paths=check_deployed_s3_paths):
                confirmation.confirm(self.stack, self.environment, start=self.start)

            self.assertEqual(len(check_sns.mock_calls), 0)
            self.assertEqual(len(check_url.mock_calls), 0)
            self.assertEqual(len(check_deployed_s3_paths.mock_calls), 0)

        it "complains if there are 0 instances and not zero_instances_is_ok":
            instances = mock.MagicMock(name="instances", __len__=lambda *args: 0)
            stack_name = mock.Mock(name="stack_name")
            confirmation = BespinSpec().confirm_deployment_spec.normalise(Meta({}, []), {"auto_scaling_group_name":"whatever", "zero_instances_is_ok": False})
            self.stack.name = stack_name
            with self.fuzzyAssertRaisesError(BadDeployment, "No instances are InService in the auto scaling group!", stack=stack_name, auto_scaling_group_name="whatever"):
                with mock.patch.object(confirmation, "instances", lambda *args: instances):
                    confirmation.confirm(self.stack, self.environment, start=self.start)

    describe "instances":
        it "asks cloudformation for the logical id and ec2 for the InService instances":
            ec2 = mock.Mock(name="ec2")
            instances = mock.Mock(name="instances")
            logical_id = mock.Mock(name="logical_id")
            cloudformation = mock.Mock(name="cloudformation")

            ec2.get_instances_in_asg_by_lifecycle_state.return_value = instances
            cloudformation.map_logical_to_physical_resource_id.return_value = logical_id

            self.stack.ec2 = ec2
            self.stack.cloudformation = cloudformation

            confirmation = BespinSpec().confirm_deployment_spec.normalise(Meta({}, []), {"auto_scaling_group_name":"whatever"})
            self.assertIs(confirmation.instances(self.stack), instances)

            cloudformation.map_logical_to_physical_resource_id.assert_called_once_with("whatever")
            ec2.get_instances_in_asg_by_lifecycle_state.assert_called_once_with(logical_id, lifecycle_state="InService")
