"""
We use this formatter to lookup options in the configuration from strings.

So normally, strings are formatted as follows::

    "blah {0}".format(1) == "blah 1"

What we want is something like this::

    configuration = {"folders": {"root": "/somewhere"}}
    "blah {folders.root}".format() == "blah /somewhere"

To do this we define the MergedOptionStringFormatter below that uses the magic
of MergedOptions to do the lookup for us.
"""

from option_merge.formatter import MergedOptionStringFormatter as StringFormatter
from bespin.errors import BadOptionFormat
from input_algorithms.meta import Meta

from datetime import datetime
import six
import os

class MergedOptionStringFormatter(StringFormatter):
    """
    Resolve format options into a MergedOptions dictionary

    Usage is like:

        configuration = MergedOptions.using({"numbers": "1 two {three}", "three": 3})
        formatter = MergedOptionStringFormatter(configuration, ["numbers"])
        val = formatter.format()
        # val == "1 two 3"

    Or we can provide a value outside the configuration::

        configuration = MergedOptions.using({"one": 1, "two": 2, "three": 3})
        formatter = MergedOptionStringFormatter(configuration, ['numbers'], value="{one} {two} {three}")
        val = formatter.format()
        # val == "1 2 3"

    The formatter also has a special feature where it returns the object it finds
    if the string to be formatted is that one object::

        class dictsubclass(dict): pass
        configuration = MergedOptions.using({"some_object": dictsubclass({1:2, 3:4})}, dont_prefix=[dictsubclass])
        formatter = MergedOptionStringFormatter(configuration, [], value="{some_object}")
        val = formatter.format()
        # val == {1:2, 3:4}

    For this to work, the object must be a subclass of dict and in the dont_prefix option of the configuration.
    """

    def get_string(self, key):
        """Get a string from all_options"""
        if key not in self.all_options:
            kwargs = {}
            if len(self.chain) > 1:
                kwargs['source'] = Meta(self.all_options, self.chain[-2]).source
            raise BadOptionFormat("Can't find key in options", key=key, chain=self.chain, **kwargs)
        return super(MergedOptionStringFormatter, self).get_string(key)

    def special_get_field(self, value, args, kwargs, format_spec=None):
        """Also take the spec into account"""
        if format_spec in ("env", "underscored", "date", "config_dir"):
            return value, ()

        if value in self.chain:
            raise BadOptionFormat("Recursive option", chain=self.chain + [value])

    def special_format_field(self, obj, format_spec):
        """Know about any special formats"""
        if format_spec == "env":
            return "${{{0}}}".format(obj)

        elif format_spec == "underscored":
            return obj.replace("-", "_")

        elif format_spec == "date":
            return datetime.now().strftime(obj)

        elif format_spec == "count":
            if isinstance(obj, six.string_types):
                obj = obj.split(",")

            if isinstance(obj, list):
                return str(len(obj))
            else:
                raise BadOptionFormat("Can only :count 'list' or comma delimited 'str' type", option_path=self.option_path, got=obj)

        elif format_spec == "config_dir":
            path = self.option_path
            if obj:
                path = obj
            sources = self.all_options.source_for(path)
            if not sources:
                raise BadOptionFormat("Couldn't find config_dir for the option", option_path=self.option_path)
            return os.path.normpath(os.path.dirname(sources[0]))
