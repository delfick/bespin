from bespin.helpers import memoized_property
from bespin.amazon.mixin import AmazonMixin
from bespin.errors import StackDoesntExist

import boto.cloudformation

class StatusMeta(object):
    def __new__(cls, name, bases, attrs):
        attrs["name"] = name
        attrs["failed"] = name.endswith("FAILED")
        attrs["complete"] = name.endswith("COMPLETE")
        attrs["in_progress"] = name.endswith("IN_PROGRESS")
        attrs["cleanup_in_progress"] = name.endswith("CLEANUP_IN_PROGRESS")

        attrs["is_create"] = name.startswith("CREATE")
        attrs["is_delete"] = name.startswith("DELETE")
        attrs["is_update"] = name.startswith("UPDATE") and not name.startswith("UPDATE_ROLLBACK")
        attrs["is_rollback"] = name.startswith("ROLLBACK") or name.startswith("UPDATE_ROLLBACK")
        return type(name, bases, attrs)

class Status(object):
    exists = True
    __metaclass__ = StatusMeta

    @classmethod
    def find(kls, name):
        for cls in Status.__subclasses__():
            if cls.name == name:
                return cls
        return type(name.encode('utf-8'), (Status, ), {})

class NONEXISTANT(Status):
    exists = False
    __metaclass__ = StatusMeta

class CREATE_IN_PROGRESS(Status):
    __metaclass__ = StatusMeta
class CREATE_FAILED(Status):
    __metaclass__ = StatusMeta
class CREATE_COMPLETE(Status):
    __metaclass__ = StatusMeta

class ROLLBACK_IN_PROGRESS(Status):
    __metaclass__ = StatusMeta
class ROLLBACK_FAILED(Status):
    __metaclass__ = StatusMeta
class ROLLBACK_COMPLETE(Status):
    __metaclass__ = StatusMeta

class DELETE_IN_PROGRESS(Status):
    __metaclass__ = StatusMeta
class DELETE_FAILED(Status):
    __metaclass__ = StatusMeta
class DELETE_COMPLETE(Status):
    __metaclass__ = StatusMeta

class UPDATE_IN_PROGRESS(Status):
    __metaclass__ = StatusMeta
class UPDATE_COMPLETE_CLEANUP_IN_PROGRESS(Status):
    __metaclass__ = StatusMeta
class UPDATE_COMPLETE(Status):
    __metaclass__ = StatusMeta
class UPDATE_ROLLBACK_IN_PROGRESS(Status):
    __metaclass__ = StatusMeta
class UPDATE_ROLLBACK_FAILED(Status):
    __metaclass__ = StatusMeta
class UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS(Status):
    __metaclass__ = StatusMeta
class UPDATE_ROLLBACK_COMPLETE(Status):
    __metaclass__ = StatusMeta

class Cloudformation(AmazonMixin):
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

    @property
    def status(self):
        try:
            description = self.description()
            return Status.find(description.stack_status)
        except StackDoesntExist:
            return NONEXISTANT

