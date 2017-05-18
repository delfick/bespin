# coding: spec

from bespin.amazon.sqs import Message, SQS
from bespin.errors import BadSQSMessage

from tests.helpers import BespinCase

import boto
import mock
import json
import nose
import sys

if sys.version_info[0] == 2 and sys.version_info[1] == 6:
    # This can be removed when we can use latest Httpretty again
    def mock_sqs_deprecated(func):
        def wrapped(*args):
            raise nose.SkipTest("No moto support for python2.6 atm")
        return wrapped
else:
    from moto import mock_sqs_deprecated

describe BespinCase, "Decode Message":
    it "successfully decode a valid message":
        raw_message = "success:i-aaaaaaa:rca_contract-628-3b55f412b3016a2b955c49677e89f7e010f7fdc8"
        decoded_message = Message.decode(raw_message)
        self.assertEqual(decoded_message.result, "success")
        self.assertEqual(decoded_message.instance_id, "i-aaaaaaa")
        self.assertEqual(decoded_message.output, "rca_contract-628-3b55f412b3016a2b955c49677e89f7e010f7fdc8")

    it "can not decode a valid message":
        raw_message = "success:i-aaaaaaadsfsdfsdontract-628-3b55f412b3016a2b955c49677e89f7e010f7fdc8"
        with self.fuzzyAssertRaisesError(BadSQSMessage, "Less than two colons", msg=raw_message):
            Message.decode(raw_message)

describe BespinCase, "SQS":
    describe "get_all_deployment_messages":
        it "times out and returns nothing if we never get any messages":
            sqs = SQS()
            conn = mock.Mock(name="conn")
            conn.get_queue.return_value = mock.Mock(name="queue", count=lambda: 0)
            sqs_url = mock.Mock(name="sqs_url")
            sqs.conn = conn

            with mock.patch("time.sleep", lambda amount: None):
                self.assertEqual(sqs.get_all_deployment_messages(sqs_url, timeout=0), [])

            conn.get_queue.assert_called_once_with(sqs_url)

        it "keeps trying to get messages till it gets some valid ones":
            sleeps = []

            message1 = mock.Mock(name="message1")
            message1.get_body.return_value = json.dumps({"Message": "blah"})

            message2 = mock.Mock(name="message2")
            message2.get_body.return_value = json.dumps({"Message": "nup:"})

            message3 = mock.Mock(name="message3")
            message3.get_body.return_value = json.dumps({"Message": "success:i-1:blah-9"})

            queue = mock.Mock(name="queue")
            sqs_url = mock.Mock(name="sqs_url")

            info = {"index": -1, "responses":[[message1], [message2], [message3]]}
            def receive_message(q, number_messages):
                self.assertIs(q, queue)
                self.assertEqual(number_messages, 1)
                info["index"] += 1
                return info["responses"][info["index"]]

            conn = mock.Mock(name="conn")
            conn.get_queue.return_value = queue
            conn.receive_message.side_effect = receive_message

            queue_info = {"index": -1, "responses": [0, 0, 1, 0, 2, 1, 0]}
            def count():
                queue_info["index"] += 1
                return queue_info["responses"][queue_info["index"]]
            queue.count.side_effect = count

            def sleep(amount):
                sleeps.append(amount)

            sqs = SQS()
            sqs.conn = conn
            with mock.patch("time.sleep", sleep):
                self.assertEqual(sqs.get_all_deployment_messages(sqs_url), [Message.decode("success:i-1:blah-9")])

            conn.get_queue.assert_called_once_with(sqs_url)
            self.assertEqual(sleeps, [2, 2, 2])
            self.assertEqual(queue.delete_message.mock_calls, [mock.call(message1), mock.call(message2), mock.call(message3)])

        @mock_sqs_deprecated
        it "works with the sqs api":
            conn = boto.connect_sqs()
            sqs = SQS()
            sqs.conn = conn

            queue = conn.create_queue("whatever")
            messages = ["success:i-1:blah", "failure:i-2:blah", "success:i-3:blah", "successi-3blah", "success:i-4:blah"]

            for msg in messages:
                queue.write(queue.new_message(json.dumps({"Message": msg})))

            found = sqs.get_all_deployment_messages("whatever")
            self.assertEqual(found, [Message.decode(msg) for msg in messages if msg.count(":") == 2])
            self.assertEqual(len(found), 4)
