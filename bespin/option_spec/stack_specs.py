"""
Custom specifications for the different types of stack options.

The idea is that these understand the conditions around representation of the
options.
"""

from bespin.option_spec.stack_objs import StaticVariable, DynamicVariable, Environment, Skipper, S3Address
from bespin.option_spec.specs import many_item_formatted_spec
from bespin.option_spec.artifact_objs import ArtifactCommand
from bespin.option_spec.artifact_objs import ArtifactPath
from bespin.formatter import MergedOptionStringFormatter
from bespin.errors import BadSpecValue

from input_algorithms.spec_base import NotSpecified
from input_algorithms import spec_base as sb
from six.moves.urllib.parse import urlparse

class var_spec(many_item_formatted_spec):
    value_name = "Variable"
    specs = [sb.string_or_int_as_string_spec()]
    optional_specs = [sb.string_or_int_as_string_spec()]
    formatter = MergedOptionStringFormatter
    seperators = "|"

    def create_result(self, variable, variable_value, meta, val, dividers):
        if variable_value is NotSpecified:
            return StaticVariable(variable)
        else:
            stack = variable
            return DynamicVariable(stack, variable_value, meta.everything["bespin"])

class artifact_path_spec(many_item_formatted_spec):
    value_name = "Artifact Path"
    specs = [sb.string_spec(), sb.string_spec()]
    formatter = MergedOptionStringFormatter

    def create_result(self, host_path, artifact_path, meta, val, dividers):
        return ArtifactPath(host_path, artifact_path)

class env_spec(many_item_formatted_spec):
    value_name = "Environment Variable"
    seperators = [':', '=']

    specs = [sb.string_spec()]
    optional_specs = [sb.string_or_int_as_string_spec()]
    formatter = MergedOptionStringFormatter

    def create_result(self, env_name, other_val, meta, val, dividers):
        """Set default_val and set_val depending on the seperator"""
        args = [env_name]
        if other_val is NotSpecified:
            other_val = None
        if not dividers:
            args.extend([None, None])
        elif dividers[0] == ':':
            args.extend([other_val, None])
        elif dividers[0] == '=':
            args.extend([None, other_val])
        return Environment(*args)

class skipper_spec(many_item_formatted_spec):
    value_name = "Skip specification"
    spec = lambda: sb.delayed(var_spec())
    specs = [spec(), spec()]

    def create_result(self, var1, var2, meta, val, dividers):
        return Skipper(var1, var2)

class s3_address(many_item_formatted_spec):
    value_name = "s3 address"
    specs = [sb.string_spec()]
    optional_specs = [sb.integer_spec()]
    seperators = None
    formatter = MergedOptionStringFormatter

    def create_result(self, address, timeout, meta, val, dividers):
        if timeout is NotSpecified:
            timeout = 600

        options = urlparse(address)
        if options.scheme != "s3":
            raise BadSpecValue("Not a valid s3 address", meta=meta, got=val)
        if not options.netloc:
            path = ''
            domain = options.path
        else:
            path = options.path
            domain = options.netloc

        if not path.startswith('/'):
            path  = '/'
        return S3Address(domain, path, timeout)

formatted_string = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)

artifact_command_spec = lambda : sb.create_spec(ArtifactCommand
    , copy = sb.listof(artifact_path_spec())
    , modify = sb.dictof(sb.string_spec(), sb.set_options(append=sb.listof(formatted_string)))
    , command = formatted_string
    , add_into_tar = sb.listof(artifact_path_spec())
    )

params_json_spec = lambda: sb.listof(sb.set_options(
      ParameterKey = sb.required(sb.any_spec())
    , ParameterValue = sb.required(sb.any_spec())
    ))

params_yaml_spec = lambda: sb.dictionary_spec()

stack_json_spec = lambda: sb.set_options(
      Resources = sb.required(sb.dictof(sb.string_spec(), sb.set_options(Type=sb.required(sb.string_spec()), Properties=sb.optional_spec(sb.dictionary_spec()))))
    , Parameters = sb.optional_spec(sb.dictof(sb.string_spec(), sb.dictionary_spec()))
    , Outputs = sb.optional_spec(sb.dictof(sb.string_spec(), sb.dictionary_spec()))
    )

