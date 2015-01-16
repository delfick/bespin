from bespin.errors import BadSQSMessage

import logging
import json
import time

log = logging.getLogger("bespin.amazon.sqs")

# Get all the messages of the queue, dropping those that are not deployment messages
def get_all_deployment_messages(credentials, sqs_url, timeout=60, sleep=2):
    start = time.time()
    messages = []

    q = credentials.sqs.get_queue(sqs_url)
    while q.count() > 0 and not (time.time() - start > timeout):
        raw_messages = credentials.sqs.receive_message(q, number_messages=1)

        if len(raw_messages) > 0:
            raw_message = raw_messages[0]
            encoded_message = json.loads(raw_message.get_body())['Message']

            q.delete_message(raw_message)

            message = decode_message(encoded_message)

            if message is not None:
                messages.append(message)

        time.sleep(sleep)

    return messages

# Takes a message that is : separated and maps it to a Dict
def decode_message(encoded_message):
    # Check if this is a valid message
    if encoded_message.count(':') < 2:
        raise BadSQSMessage("Less than two colons", msg=encoded_message)

    result, instance_id, output = encoded_message.split(':', 2)
    return {
        'result': result,
        'instance_id': instance_id,
        'output': output
    }
