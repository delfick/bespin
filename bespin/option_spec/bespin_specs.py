"""
Here we define the yaml specification for Besin options, task options and stack
options.

The specifications are responsible for sanitation, validation and normalisation.
"""

from input_algorithms.spec_base import (
      formatted, defaulted, any_spec, dictionary_spec, dictof, listof, required
    , string_spec, overridden, boolean, file_spec, optional_spec, integer_spec, or_spec
    , valid_string_spec, create_spec, string_choice_spec, filename_spec as orig_filename_spec
    )

from bespin.option_spec import task_objs, stack_objs, stack_specs, artifact_objs
from bespin.formatter import MergedOptionStringFormatter
from bespin.helpers import memoized_property

from input_algorithms.dictobj import dictobj
from input_algorithms import validators

import six

class filename_spec(orig_filename_spec):
    def setup(self, spec):
        self.spec = spec

    def normalise_either(self, meta, val):
        val = self.spec.normalise(meta, val)
        return super(filename_spec, self).normalise_filled(meta, val)

class Bespin(dictobj):
    fields = ["dry_run", "flat", "config", "chosen_stack", "chosen_task", "extra", "interactive", "region", "environment"]

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
                , account_id = required(or_spec(integer_spec(), valid_string_spec(validators.regexed("\d+"))))
                , vars = dictionary_spec()
                )
            )

    @memoized_property
    def stack_spec(self):
        """Spec for each stack"""
        return create_spec(stack_objs.Stack
            , bespin = any_spec()

            , name = formatted(defaulted(string_spec(), "{_key_name_1}"), formatter=MergedOptionStringFormatter)
            , key_name = formatted(overridden("{_key_name_1}"), formatter=MergedOptionStringFormatter)
            , stack_name = formatted(defaulted(string_spec(), "{_key_name_1}"), formatter=MergedOptionStringFormatter)
            , environment = formatted(overridden("{environment}"), formatter=MergedOptionStringFormatter)

            , env = listof(stack_specs.env_spec(), expect=stack_objs.Environment)

            , stack_json = filename_spec(formatted(defaulted(string_spec(), "{config_root}/{_key_name_1}.json"), formatter=MergedOptionStringFormatter))
            , params_json = optional_spec(filename_spec(formatted(defaulted(string_spec(), "{config_root}/{environment}/{_key_name_1}-params.json"), formatter=MergedOptionStringFormatter)))

            , build_after = listof(formatted(string_spec(), formatter=MergedOptionStringFormatter))
            , ignore_deps = defaulted(boolean(), False)

            , vars = dictof(string_spec(), stack_specs.var_spec())

            , skip_update_if_equivalent = listof(stack_specs.skipper_spec())

            , artifacts = dictof(string_spec(), create_spec(artifact_objs.Artifact
                , compression_type = string_choice_spec(["gz", "xz"])
                , history_length = integer_spec()
                , location_var_name = string_spec()
                , upload_to = formatted(string_spec(), formatter=MergedOptionStringFormatter)
                , paths = listof(stack_specs.artifact_path_spec(), expect=artifact_objs.ArtifactPath)
                , files = listof(create_spec(artifact_objs.ArtifactFile
                    , content = formatted(string_spec(), formatter=MergedOptionStringFormatter)
                    , path = formatted(string_spec(), formatter=MergedOptionStringFormatter)
                    ))
                , build_env = listof(stack_specs.env_spec(), expect=stack_objs.Environment)
                ))
            )

    @memoized_property
    def bespin_spec(self):
        """Spec for bespin options"""
        formatted_string = formatted(string_spec(), MergedOptionStringFormatter, expected_type=six.string_types)
        formatted_boolean = formatted(boolean(), MergedOptionStringFormatter, expected_type=bool)

        return create_spec(Bespin
            , config = file_spec()

            , dry_run = defaulted(boolean(), False)
            , flat = defaulted(boolean(), False)
            , environment = optional_spec(string_spec())

            , extra = defaulted(formatted_string, "")
            , region = defaulted(string_spec(), "ap-southeast-2")
            , chosen_task = defaulted(formatted_string, "list_tasks")
            , chosen_stack = defaulted(formatted_string, "")

            , interactive = defaulted(formatted_boolean, True)
            )

