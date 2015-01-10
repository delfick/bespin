from bespin.helpers import memoized_property
from bespin.amazon.mixin import AmazonMixin
from bespin.errors import BadAmazon

import boto.cloudformation

class Cloudformation(object, AmazonMixin):
    def __init__(self, stack, region):
        self.stack = stack
        self.region = region

    @memoized_property
    def conn(self):
        return boto.cloudformation.connect_to_region(self.region)

    def description(self, force=False):
        """Get the descriptions for the stack"""
        if not getattr(self, "_description", None) or force:
            try:
                with self.catch_boto_400("Couldn't find stack"):
                    self._description = self.conn.describe_stacks(self.stack.stack_name)[0]
            except BadAmazon:
                self._description = None
        return self._description

    @property
    def outputs(self):
        description = self.description()
        if description is None:
            return {}
        else:
            return dict((out.key, out.value) for out in description.outputs)

