from bespin.helpers import memoized_property
from bespin.errors import BadSQSMessage

import boto.sqs

import logging
import json
import time

log = logging.getLogger("bespin.amazon.sqs")

class SQS(object):
    def __init__(self, region="ap-southeast-2"):
        self.region = region

    @memoized_property
    def conn(self):
        log.info("Using region [%s] for sqs", self.region)
        return boto.sqs.connect_to_region(self.region)

    def get_all_deployment_messages(self, sqs_url, timeout=60, sleep=2):
        """Get all the messages of the queue, dropping those that are not deployment messages"""
        start = time.time()
        messages = []

        q = self.conn.get_queue(sqs_url)
        while q.count() > 0 and not (time.time() - start > timeout):
            raw_messages = self.conn.receive_message(q, number_messages=1)

            if len(raw_messages) > 0:
                raw_message = raw_messages[0]
                encoded_message = json.loads(raw_message.get_body())['Message']

                q.delete_message(raw_message)

                message = self.decode_message(encoded_message)

                if message is not None:
                    messages.append(message)

            time.sleep(sleep)

        return messages

    def decode_message(self, encoded_message):
        """Takes a message that is : separated and maps it to a Dict"""
        if encoded_message.count(':') < 2:
            raise BadSQSMessage("Less than two colons", msg=encoded_message)

        result, instance_id, output = encoded_message.split(':', 2)
        return {'result': result, 'instance_id': instance_id, 'output': output }

