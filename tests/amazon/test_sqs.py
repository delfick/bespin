# coding: spec

from bespin.errors import BadSQSMessage
from bespin.amazon.sqs import SQS

from tests.helpers import BespinCase

describe BespinCase, "Decode Message":
    it "successfully decode a valid message":
        raw_message = "success:i-aaaaaaa:rca_contract-628-3b55f412b3016a2b955c49677e89f7e010f7fdc8"
        decoded_message = SQS().decode_message(raw_message)
        self.assertEqual(decoded_message['result'], "success")
        self.assertEqual(decoded_message['instance_id'], "i-aaaaaaa")
        self.assertEqual(decoded_message['output'], "rca_contract-628-3b55f412b3016a2b955c49677e89f7e010f7fdc8")

    it "can not decode a valid message":
        raw_message = "success:i-aaaaaaadsfsdfsdontract-628-3b55f412b3016a2b955c49677e89f7e010f7fdc8"
        with self.fuzzyAssertRaisesError(BadSQSMessage, "Less than two colons", msg=raw_message):
            SQS().decode_message(raw_message)
