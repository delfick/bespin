"""
Here we define the yaml specification for Besin options, task options and stack
options.

The specifications are responsible for sanitation, validation and normalisation.
"""

from input_algorithms.spec_base import (
      formatted, defaulted, any_spec, dictionary_spec, dictof, listof, required, delayed
    , string_spec, overridden, boolean, file_spec, optional_spec, integer_spec, or_spec, container_spec
    , valid_string_spec, create_spec, string_choice_spec, Spec, always_same_spec, match_spec
    )

from bespin.option_spec import task_objs, stack_objs, stack_specs, artifact_objs, imports, deployment_check, netscaler as netscaler_specs
from bespin.option_spec.netscaler import valid_environment_spec
from bespin.formatter import MergedOptionStringFormatter
from bespin.errors import BadFile, BadConfiguration
from bespin.option_spec.bespin_obj import Bespin
from bespin.helpers import memoized_property

from input_algorithms.spec_base import NotSpecified
from input_algorithms.validators import Validator
from input_algorithms.errors import BadSpecValue
from input_algorithms.dictobj import dictobj
from input_algorithms import validators

import json
import yaml
import six
import os

class has_params_specified(Validator):
    """Takes in a stack object and makes sure we have parameters"""
    def setup(self, spec):
        self.spec = spec

    def validate(self, meta, val):
        val = self.spec.normalise(meta, val)
        is_obj = lambda item: item and isinstance(item, list) or (isinstance(item, dict) or getattr(item, "is_dict", False))
        is_file = lambda item: item and (isinstance(item, six.string_types) and os.path.exists(item))

        params_json = val.params_json
        params_yaml = val.params_yaml

        if      (not is_obj(params_json) and not is_file(params_json)) \
            and (not is_obj(params_yaml) and not is_file(params_yaml)):
          raise BadSpecValue("Please specify either params_json or params_yaml for each stack", meta=meta)

        return val

class valid_params(Spec):
    filetype = NotImplemented
    params_spec = NotImplemented

    def setup(self, default):
        self.dflt = default

    def normalise_either(self, meta, val):
        if isinstance(val, six.string_types) or val is NotSpecified:
            val = formatted(defaulted(string_spec(), self.dflt), formatter=MergedOptionStringFormatter).normalise(meta, val)
            if os.path.exists(val):
                try:
                    with open(val) as fle:
                        val = self.filetype.load(fle)
                except (ValueError, TypeError) as error:
                    raise BadFile(error, filename=val, meta=meta)
                self.params_spec().normalise(meta, val)
            else:
                val = NotSpecified
        else:
            self.params_spec().normalise(meta, val)

        return val

class valid_params_json(valid_params):
    filetype = json
    params_spec = lambda k: stack_specs.params_json_spec()

class valid_params_yaml(valid_params):
    filetype = yaml
    params_spec = lambda k: stack_specs.params_yaml_spec()

class valid_stack_json(valid_params):
    filetype = json
    params_spec = lambda k: stack_specs.stack_json_spec()

class valid_alerting_system(Spec):
    def normalise_filled(self, meta, val):
        if meta.everything.get("alerting_systems", NotSpecified) is NotSpecified:
            raise BadConfiguration("No alerting systems have been specified")

        available = list(meta.everything["alerting_systems"].keys())
        if val not in available:
            raise BadConfiguration("Unknown alerting system, please define it under {alerting_systems}", name=val, available=available)

        return val

class valid_password_key(Spec):
    def normalise_filled(self, meta, val):
        if meta.everything.get("passwords", NotSpecified) is NotSpecified:
            raise BadConfiguration("No password options have been specified")

        available = list(meta.everything["passwords"].keys())
        if val not in available:
            raise BadConfiguration("Unknown password, please define it under {passwords}", name=val, available=available)

        return val

class copy_environment_spec(Spec):
    def normalise_filled(self, meta, val):
        available = list(meta.everything["environments"].keys())
        if val not in available:
            raise BadConfiguration("Trying to copy an environment that doesn't exist", available=available, wanted=val)

        return BespinSpec().environment_spec.normalise(meta, meta.everything["environments"].as_dict()[val])

class Environment(dictobj):
    fields = ["account_id", "vars", "region"]

class other_options(dictobj):
    fields = ["run", "create", "build"]

class ScalingOptions(dictobj):
    fields = ["highest_min", "instance_count_limit"]

class BespinSpec(object):
    """Knows about bespin specific configuration"""

    @memoized_property
    def task_name_spec(self):
        """Just needs to be ascii"""
        return valid_string_spec(
              validators.no_whitespace()
            , validators.regexed("^[a-zA-Z][a-zA-Z0-9-_\.]*$")
            )

    def tasks_spec(self, available_actions, default_action="run"):
        """Tasks for a particular stack"""
        return dictof(
              self.task_name_spec
            , create_spec(task_objs.Task
                , action = defaulted(string_choice_spec(available_actions, "No such task"), default_action)
                , options = dictionary_spec()
                , overrides = dictionary_spec()
                , description = string_spec()
                )
            )

    @memoized_property
    def plans_spec(self):
        """Spec for plans"""
        return dictof(
              string_spec()
            , listof(string_spec())
            )

    @memoized_property
    def environments_spec(self):
        """Spec for each environment options"""
        return dictof(
              string_spec()
            , match_spec((str, copy_environment_spec()), (dict, self.environment_spec))
            )

    @memoized_property
    def environment_spec(self):
        """Spec for each environment"""
        return create_spec(Environment
            , account_id = required(or_spec(string_spec(), valid_string_spec(validators.regexed("\d+"))))
            , region = defaulted(string_spec(), "ap-southeast-2")
            , vars = dictionary_spec()
            )

    @memoized_property
    def url_checker_spec(self):
        return create_spec(deployment_check.UrlChecker
            , check_url = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
            , endpoint = required(delayed(stack_specs.var_spec()))
            , expect = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
            , timeout_after = defaulted(integer_spec(), 600)
            )

    @memoized_property
    def confirm_deployment_spec(self):
        return create_spec(deployment_check.ConfirmDeployment
            , deploys_s3_path = optional_spec(listof(stack_specs.s3_address()))
            , zero_instances_is_ok = defaulted(boolean(), False)
            , auto_scaling_group_name = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))

            , url_checker = optional_spec(self.url_checker_spec)

            , sns_confirmation = optional_spec(create_spec(deployment_check.SNSConfirmation
                , validators.deprecated_key("auto_scaling_group_id", "Use ``confirm_deployment.auto_scaling_group_name``")
                , validators.deprecated_key("env", "Use ``stack.<stack>.env`` instead``")

                , timeout = defaulted(integer_spec(), 300)
                , version_message = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                , deployment_queue = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                ))
            )

    @memoized_property
    def alerting_system_spec(self):
        return create_spec(stack_objs.AlertingSystem
            , name = formatted(overridden("{_key_name_1}"), formatter=MergedOptionStringFormatter)
            , type = string_choice_spec(["nagios"])
            , endpoint = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
            , verify_ssl = defaulted(boolean(), True)
            )

    @memoized_property
    def password_spec(self):
        formatted_string = formatted(string_spec(), formatter=MergedOptionStringFormatter)
        return create_spec(stack_objs.Password
            , name = formatted(overridden("{_key_name_1}"), formatter=MergedOptionStringFormatter)
            , bespin = formatted(overridden("{bespin}"), formatter=MergedOptionStringFormatter)

            , KMSMasterKey = required(formatted_string)
            , encryption_context = optional_spec(dictionary_spec())
            , grant_tokens = optional_spec(listof(formatted_string))
            , crypto_text = required(formatted_string)

            , vars = dictionary_spec()
            )

    @memoized_property
    def netscaler_spec(self):
        class to_boolean(Spec):
            def setup(self, spec):
                self.spec = spec

            def normalise_either(self, meta, val):
                val = self.spec.normalise(meta, val)

                if type(val) is bool:
                    return val

                if val == 'False':
                    return False
                elif val == 'True':
                    return True
                raise BadConfiguration("Expected a boolean", got=val, meta=meta)

        return create_spec(netscaler_specs.NetScaler
            , host = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
            , dry_run = to_boolean(formatted(overridden("{bespin.dry_run}"), formatter=MergedOptionStringFormatter))

            , username = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
            , configuration_username = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))

            , password = delayed(required(formatted(string_spec(), formatter=MergedOptionStringFormatter)))
            , configuration_password = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))

            , verify_ssl = defaulted(boolean(), True)
            , nitro_api_version = defaulted(formatted(string_spec(), formatter=MergedOptionStringFormatter), "v1")
            , configuration = optional_spec(netscaler_specs.configuration_spec())
            , syncable_environments = optional_spec(listof(valid_environment_spec()))
            )

    @memoized_property
    def stack_spec(self):
        """Spec for each stack"""
        return has_params_specified(create_spec(stack_objs.Stack
            , validators.deprecated_key("url_checker", "Use ``confirm_deployment.url_checker1``")
            , validators.deprecated_key("deploys_s3_path", "Use ``confirm_deployment.deploys_s3_path``")
            , validators.deprecated_key("sns_confirmation", "Use ``confirm_deployment.sns_confirmation``")
            , validators.deprecated_key("autoscaling_group_id", "Use ``auto_scaling_group_name``")
            , validators.deprecated_key("instance_count_limit", "Use ``scaling_options.instance_count_limit``")

            , bespin = any_spec()

            , name = formatted(defaulted(string_spec(), "{_key_name_1}"), formatter=MergedOptionStringFormatter)
            , key_name = formatted(overridden("{_key_name_1}"), formatter=MergedOptionStringFormatter)
            , stack_name = formatted(defaulted(string_spec(), "{_key_name_1}"), formatter=MergedOptionStringFormatter)
            , environment = formatted(overridden("{environment}"), formatter=MergedOptionStringFormatter)

            , env = listof(stack_specs.env_spec(), expect=stack_objs.Environment)
            , build_env = listof(stack_specs.env_spec(), expect=stack_objs.Environment)
            , stack_name_env = listof(stack_specs.env_spec(), expect=stack_objs.Environment)

            , tags = dictionary_spec()

            , stack_json = valid_stack_json(default="{config_root}/{_key_name_1}.json")

            , params_json = valid_params_json(default="{config_root}/{environment}/{_key_name_1}-params.json")
            , params_yaml = valid_params_yaml(default="{config_root}/{environment}/{_key_name_1}-params.yaml")

            , build_first = listof(formatted(string_spec(), formatter=MergedOptionStringFormatter))
            , build_after = listof(formatted(string_spec(), formatter=MergedOptionStringFormatter))
            , build_timeout = defaulted(integer_spec(), 1200)
            , ignore_deps = defaulted(boolean(), False)

            , vars = delayed(dictof(string_spec(), stack_specs.var_spec(), nested=True))

            , skip_update_if_equivalent = listof(stack_specs.skipper_spec())

            , suspend_actions = defaulted(boolean(), False)
            , auto_scaling_group_name = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))

            , artifact_retention_after_deployment = defaulted(boolean(), False)

            , command = optional_spec(string_spec())

            , netscaler = optional_spec(self.netscaler_spec)

            , notify_stackdriver = defaulted(boolean(), False)

            , stackdriver = optional_spec(create_spec(stack_objs.Stackdriver
                , api_key = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                , deployment_version = defaulted(formatted(string_spec(), formatter=MergedOptionStringFormatter), "<version>")
                ))

            , dns = optional_spec(stack_specs.dns_spec(create_spec(stack_objs.DNS
                , vars = dictof(string_spec(), formatted(string_spec(), formatter=MergedOptionStringFormatter), nested=True)
                , providers = dictof(string_spec(), stack_specs.dns_provider_spec())
                , sites = delayed(dictof(string_spec(), stack_specs.dns_site_spec()))
                )))

            , scaling_options = create_spec(ScalingOptions
                , highest_min = defaulted(integer_spec(), 2)
                , instance_count_limit = defaulted(integer_spec(), 10)
                )

            , artifacts = container_spec(artifact_objs.ArtifactCollection, dictof(string_spec(), create_spec(artifact_objs.Artifact
                , not_created_here = defaulted(boolean(), False)
                , compression_type = string_choice_spec(["gz", "xz"])
                , history_length = integer_spec()
                , cleanup_prefix = optional_spec(string_spec())
                , upload_to = formatted(string_spec(), formatter=MergedOptionStringFormatter)
                , commands = listof(stack_specs.artifact_command_spec(), expect=artifact_objs.ArtifactCommand)
                , paths = listof(stack_specs.artifact_path_spec(), expect=artifact_objs.ArtifactPath)
                , files = listof(create_spec(artifact_objs.ArtifactFile, validators.has_either(["content", "task"])
                    , content = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                    , task = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                    , path = formatted(string_spec(), formatter=MergedOptionStringFormatter)
                    , task_runner = formatted(always_same_spec("{task_runner}"), formatter=MergedOptionStringFormatter)
                    ))
                )))

            , newrelic = optional_spec(create_spec(stack_objs.NewRelic
                , api_key = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                , account_id = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                , application_id = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))

                , env = listof(stack_specs.env_spec(), expect=stack_objs.Environment)
                , deployed_version = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                ))

            , downtimer_options = optional_spec(dictof(valid_string_spec(valid_alerting_system())
                , create_spec(stack_objs.DowntimerOptions
                    , hosts = listof(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                    )
                ))

            , alerting_systems = optional_spec(dictof(string_spec(), self.alerting_system_spec))

            , ssh = optional_spec(create_spec(stack_objs.SSH
                , validators.deprecated_key("autoscaling_group_id", "Use ``auto_scaling_group_name``")

                , user = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                , bastion = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                , bastion_user = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                , bastion_key_location = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                , instance_key_location = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))

                , address = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                , instance = optional_spec(listof(formatted(string_spec(), formatter=MergedOptionStringFormatter)))
                , auto_scaling_group_name = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))

                , bastion_key_path = formatted(defaulted(string_spec(), "{config_root}/{environment}/bastion_ssh_key.pem"), formatter=MergedOptionStringFormatter)
                , instance_key_path = formatted(defaulted(string_spec(), "{config_root}/{environment}/ssh_key.pem"), formatter=MergedOptionStringFormatter)

                , storage_type = formatted(defaulted(string_choice_spec(["url", "rattic"]), "url"), formatter=MergedOptionStringFormatter)
                , storage_host = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                ))

            , confirm_deployment = optional_spec(self.confirm_deployment_spec)
            ))

    @memoized_property
    def bespin_spec(self):
        """Spec for bespin options"""
        formatted_string = formatted(string_spec(), MergedOptionStringFormatter, expected_type=six.string_types)
        formatted_boolean = formatted(boolean(), MergedOptionStringFormatter, expected_type=bool)

        return create_spec(Bespin
            , validators.deprecated_key("region", "Please use ``environments.<env>.region``")

            , config = file_spec()
            , configuration = any_spec()

            , assume_role = optional_spec(string_spec())

            , extra = defaulted(string_spec(), "")
            , dry_run = defaulted(boolean(), False)
            , flat = defaulted(boolean(), False)
            , environment = optional_spec(string_spec())

            , no_assume_role = defaulted(formatted_boolean, False)

            , chosen_task = defaulted(formatted_string, "list_tasks")
            , chosen_stack = defaulted(formatted_string, "")
            , chosen_artifact = defaulted(formatted_string, "")

            , extra_imports = listof(imports.import_spec())
            )

