"""
Custom specifications for the different types of stack options.

The idea is that these understand the conditions around representation of the
options.
"""

from bespin.option_spec.stack_objs import (
      StaticVariable, DynamicVariable, Environment, Skipper, S3Address
    , UltraDNSSite, UltraDNSProvider
    )
from bespin.option_spec.artifact_objs import ArtifactCommand
from bespin.option_spec.artifact_objs import ArtifactPath
from bespin.formatter import MergedOptionStringFormatter
from bespin.errors import BadSpecValue, BadConfiguration
from bespin.helpers import memoized_property

from input_algorithms.many_item_spec import many_item_formatted_spec
from input_algorithms.spec_base import NotSpecified, Spec
from input_algorithms import spec_base as sb
from six.moves.urllib.parse import urlparse
import logging

log = logging.getLogger("bespin.option_spec.stack_specs")

class var_spec(many_item_formatted_spec):
    value_name = "Variable"
    specs = [sb.or_spec(sb.string_or_int_as_string_spec(), sb.listof(sb.string_or_int_as_string_spec()))]
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
    creates = ArtifactPath
    formatter = MergedOptionStringFormatter

    def create_result(self, host_path, artifact_path, meta, val, dividers):
        return ArtifactPath(host_path, artifact_path)

class env_spec(many_item_formatted_spec):
    value_name = "Environment Variable"
    seperators = [':', '=']

    specs = [sb.string_spec()]
    creates = Environment
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
    creates = Skipper
    specs = [spec(), spec()]

    def create_result(self, var1, var2, meta, val, dividers):
        return Skipper(var1, var2)

class s3_address(many_item_formatted_spec):
    value_name = "s3 address"
    specs = [sb.string_spec()]
    optional_specs = [sb.integer_spec()]
    creates = S3Address
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

class dns_spec(Spec):
    def setup(self, spec):
        self.spec = spec

    def normalise_filled(self, meta, val):
        meta.everything = meta.everything.wrapped()
        meta.everything["__dns_vars__"] = val["vars"].as_dict()
        return self.spec.normalise(meta, val)

class dns_site_spec(Spec):
    def normalise_filled(self, meta, val):
        log.info("Normalising dns site %s", meta.path)
        val = sb.dictionary_spec().normalise(meta, val)
        provider = val["provider"]
        available = meta.everything["stacks"][meta.everything["__stack_name__"]]["dns"]["providers"]
        if provider not in available.keys():
            raise BadConfiguration("Specified provider isn't defined in {dns.providers}", available=list(available.keys()), wanted=provider, meta=meta)

        val["provider"] = lambda: meta.everything["stacks"][meta.everything["__stack_name__"]]["dns"]["providers"][provider]
        if available[provider]["provider_type"] == "ultradns":
            return self.ultradns_site_spec(val).normalise(meta, val)
        else:
            raise BadConfiguration("Unknown dns provider type", available=["ultradns"], wanted=val["provider"].provider_type, meta=meta)

    def ultradns_site_spec(self, this):
        formatted_string = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)
        return sb.create_spec(UltraDNSSite
            , name = sb.formatted(sb.overridden("{_key_name_1}"), formatter=MergedOptionStringFormatter)
            , ttl = sb.optional_spec(sb.integer_spec())
            , provider = sb.any_spec()
            , record_type = sb.required(formatted_string)
            , zone = sb.required(formatted_string)
            , domain = sb.required(formatted_string)
            , environments = sb.required(self.dns_environment_spec(this))
            )

    def dns_environment_spec(self, this):
        formatted_string = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)
        class spec(Spec):
            def normalise_filled(s, meta, val):
                meta.everything = meta.everything.wrapped()
                meta.everything["__site_environments__"] = this["environments"].as_dict()
                spec = sb.dictof(sb.string_spec(), sb.listof(formatted_string))
                return spec.normalise(meta, val.as_dict())
        return spec()

class dns_provider_spec(Spec):
    def normalise_filled(self, meta, val):
        val = sb.dictionary_spec().normalise(meta, val)
        provider_type = val["provider_type"]
        available = ["ultradns"]
        if provider_type not in available:
            raise BadConfiguration("Specified provider type isn't supported", supported=available, wanted=provider_type, meta=meta)

        if provider_type == "ultradns":
            return self.ultradns_provider_spec.normalise(meta, val)

    @memoized_property
    def ultradns_provider_spec(self):
        return sb.create_spec(UltraDNSProvider
            , name = sb.formatted(sb.overridden("{_key_name_1}"), formatter=MergedOptionStringFormatter)
            , provider_type = sb.required(sb.string_spec())
            , username = sb.required(formatted_string)
            , password = sb.required(formatted_string)
            )

formatted_string = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)

artifact_command_spec = lambda : sb.create_spec(ArtifactCommand
    , copy = sb.listof(artifact_path_spec())
    , modify = sb.dictof(sb.string_spec(), sb.set_options(append=sb.listof(formatted_string)))
    , command = sb.listof(formatted_string)
    , timeout = sb.defaulted(sb.integer_spec(), 600)
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

