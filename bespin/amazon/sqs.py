from bespin.helpers import memoized_property, until
from bespin.errors import BadSQSMessage

import boto.sqs

from collections import namedtuple
import logging
import json

log = logging.getLogger("bespin.amazon.sqs")

class Message(namedtuple("Message", ["result", "instance_id", "output"])):
    @classmethod
    def decode(kls, message):
        """Takes a message that is : separated and maps it an instance of Message"""
        if message.count(':') < 2:
            raise BadSQSMessage("Less than two colons", msg=message)

        result, instance_id, output = message.split(':', 2)
        return kls(result=result, instance_id=instance_id, output=output)

class SQS(object):
    def __init__(self, region="ap-southeast-2"):
        self.region = region

    @memoized_property
    def conn(self):
        log.info("Using region [%s] for sqs", self.region)
        return boto.sqs.connect_to_region(self.region)

    def get_all_deployment_messages(self, sqs_url, timeout=60, sleep=2):
        """
        Get all the messages of the queue, dropping those that are not deployment messages

        We keep getting messages whilst the count is greater than 0 and we don't have messages yet.

        We will eventually timeout and return what we have if we keep getting invalid messages or keep getting no messages.
        """
        messages = []
        q = self.conn.get_queue(sqs_url)
        for _ in until(timeout, step=sleep):
            while q.count() > 0:
                raw_messages = self.conn.receive_message(q, number_messages=1)
                for raw_message in raw_messages:
                    encoded_message = json.loads(raw_message.get_body())['Message']

                    q.delete_message(raw_message)

                    try:
                        messages.append(Message.decode(encoded_message))
                    except BadSQSMessage as error:
                        log.error("Failed to parse a message: %s", error)

            if messages:
                break

        return messages

