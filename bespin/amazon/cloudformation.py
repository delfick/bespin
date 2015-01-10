from bespin.errors import BadAmazon, StackDoesntExist
from bespin.helpers import memoized_property
from bespin.amazon.mixin import AmazonMixin

import boto.cloudformation

class Cloudformation(object, AmazonMixin):
    def __init__(self, stack_name, region):
        self.region = region
        self.stack_name = stack_name

    @memoized_property
    def conn(self):
        return boto.cloudformation.connect_to_region(self.region)

    def description(self, force=False):
        """Get the descriptions for the stack"""
        if not getattr(self, "_description", None) or force:
            with self.catch_boto_400(StackDoesntExist, "Couldn't find stack"):
                self._description = self.conn.describe_stacks(self.stack_name)[0]
        return self._description

    @property
    def outputs(self):
        description = self.description()
        if description is None:
            return {}
        else:
            return dict((out.key, out.value) for out in description.outputs)

