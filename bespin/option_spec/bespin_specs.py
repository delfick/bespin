"""
Here we define the yaml specification for Besin options, task options and stack
options.

The specifications are responsible for sanitation, validation and normalisation.
"""

from input_algorithms.spec_base import (
      formatted, defaulted, any_spec, dictionary_spec, dictof, listof, required, delayed
    , string_spec, overridden, boolean, file_spec, optional_spec, integer_spec, or_spec, container_spec
    , valid_string_spec, create_spec, string_choice_spec, Spec
    )

from bespin.option_spec import task_objs, stack_objs, stack_specs, artifact_objs, imports, deployment_check
from bespin.formatter import MergedOptionStringFormatter
from bespin.option_spec.bespin_obj import Bespin
from bespin.helpers import memoized_property
from bespin.errors import BadFile

from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj
from input_algorithms import validators

import json
import yaml
import six
import os

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

class Environment(dictobj):
    fields = ["account_id", "vars"]

class other_options(dictobj):
    fields = ["run", "create", "build"]

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
    def environments_spec(self):
        """Spec for each environment options"""
        return dictof(
              string_spec()
            , create_spec(Environment
                , account_id = required(or_spec(string_spec(), valid_string_spec(validators.regexed("\d+"))))
                , vars = dictionary_spec()
                )
            )

    @memoized_property
    def stack_spec(self):
        """Spec for each stack"""
        return create_spec(stack_objs.Stack
            , validators.deprecated_key("url_checker", "Use ``confirm_deployment.url_checker1``")
            , validators.deprecated_key("deploys_s3_path", "Use ``confirm_deployment.deploys_s3_path``")
            , validators.deprecated_key("sns_confirmation", "Use ``confirm_deployment.sns_confirmation``")
            , validators.deprecated_key("autoscaling_group_id", "Use ``auto_scaling_group_name``")

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
            , ignore_deps = defaulted(boolean(), False)

            , vars = dictof(string_spec(), stack_specs.var_spec())

            , skip_update_if_equivalent = listof(stack_specs.skipper_spec())

            , suspend_actions = defaulted(boolean(), False)
            , auto_scaling_group_name = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))

            , artifact_retention_after_deployment = defaulted(boolean(), False)

            , command = optional_spec(string_spec())

            , instance_count_limit = defaulted(integer_spec(), 10)

            , artifacts = container_spec(artifact_objs.ArtifactCollection, dictof(string_spec(), create_spec(artifact_objs.Artifact
                , compression_type = string_choice_spec(["gz", "xz"])
                , history_length = integer_spec()
                , upload_to = formatted(string_spec(), formatter=MergedOptionStringFormatter)
                , commands = listof(stack_specs.artifact_command_spec(), expect=artifact_objs.ArtifactCommand)
                , paths = listof(stack_specs.artifact_path_spec(), expect=artifact_objs.ArtifactPath)
                , files = listof(create_spec(artifact_objs.ArtifactFile
                    , content = formatted(string_spec(), formatter=MergedOptionStringFormatter)
                    , path = formatted(string_spec(), formatter=MergedOptionStringFormatter)
                    ))
                )))

            , ssh = optional_spec(create_spec(stack_objs.SSH
                , validators.deprecated_key("autoscaling_group_id", "Use ``auto_scaling_group_name``")

                , user = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                , bastion = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                , bastion_key_location = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                , instance_key_location = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))

                , address = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                , instance = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                , auto_scaling_group_name = optional_spec(formatted(string_spec(), formatter=MergedOptionStringFormatter))

                , bastion_key_path = formatted(defaulted(string_spec(), "{config_root}/{environment}/bastion_ssh_key.pem"), formatter=MergedOptionStringFormatter)
                , instance_key_path = formatted(defaulted(string_spec(), "{config_root}/{environment}/ssh_key.pem"), formatter=MergedOptionStringFormatter)
                ))

            , confirm_deployment = optional_spec(create_spec(deployment_check.ConfirmDeployment
                , deploys_s3_path = optional_spec(listof(stack_specs.s3_address()))
                , zero_instances_is_ok = defaulted(boolean(), False)
                , auto_scaling_group_name = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))

                , url_checker = optional_spec(create_spec(deployment_check.UrlChecker
                    , check_url = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                    , endpoint = required(delayed(stack_specs.var_spec()))
                    , expect = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                    , timeout_after = defaulted(integer_spec(), 600)
                    ))

                , sns_confirmation = optional_spec(create_spec(deployment_check.SNSConfirmation
                    , validators.deprecated_key("auto_scaling_group_id", "Use ``confirm_deployment.auto_scaling_group_name``")

                    , env = listof(stack_specs.env_spec(), expect=stack_objs.Environment)
                    , timeout = defaulted(integer_spec(), 300)
                    , version_message = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                    , deployment_queue = required(formatted(string_spec(), formatter=MergedOptionStringFormatter))
                    ))
                ))
            )

    @memoized_property
    def bespin_spec(self):
        """Spec for bespin options"""
        formatted_string = formatted(string_spec(), MergedOptionStringFormatter, expected_type=six.string_types)
        formatted_boolean = formatted(boolean(), MergedOptionStringFormatter, expected_type=bool)

        return create_spec(Bespin
            , config = file_spec()
            , configuration = any_spec()

            , assume_role = optional_spec(string_spec())

            , dry_run = defaulted(boolean(), False)
            , flat = defaulted(boolean(), False)
            , environment = optional_spec(string_spec())

            , extra = defaulted(formatted_string, "")
            , region = defaulted(string_spec(), "ap-southeast-2")
            , no_assume_role = defaulted(formatted_boolean, False)

            , chosen_task = defaulted(formatted_string, "list_tasks")
            , chosen_stack = defaulted(formatted_string, "")
            , chosen_artifact = defaulted(formatted_string, "")

            , extra_imports = listof(imports.import_spec())
            )

