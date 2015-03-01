# coding: spec

from bespin.option_spec.deployment_check import SNSConfirmation
from bespin.option_spec.bespin_specs import BespinSpec
from bespin.errors import BadStack, BadDeployment
from bespin.amazon.sqs import Message

from tests.helpers import BespinCase

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
            sleep = mock.Mock(name="sleep")

            with self.fuzzyAssertRaisesError(BadDeployment, "Failed to receive any messages"):
                with mock.patch("time.sleep", sleep):
                    confirmation = SNSConfirmation(version_message="{VAR}*", deployment_queue=queue, timeout=0)
                    confirmation.wait(["i-1", "i-2", "i-3", "i-4"], {"VAR": "blah"}, sqs)

