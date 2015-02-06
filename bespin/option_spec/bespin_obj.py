from bespin.errors import BadOption, BadOptionFormat, MissingVariable
from bespin.option_spec import stack_objs

from input_algorithms.dictobj import dictobj
from option_merge import MergedOptions
from itertools import chain
import string
import six

class Bespin(dictobj):
    fields = {
        "flat": "Used by the ``Show`` task to show the stacks as a flat list. Set by ``--flat``"
      , "extra": "Holds the extra command line arguments after ``--``"
      , "config": "Holds a file object to the specified Bespin configuration file"
      , "region": "The amazon region to perform actions in"
      , "dry_run": "Don't run any destructive or modification amazon requests"
      , "assume_role": """
            An iam role to assume into before doing any amazon requests.

            This behaviour can be disabled by setting the ``NO_ASSUME_ROLE``
            environment variable to any value.
        """
      , "environment": """
            The environment in the configuration to use.

            When a stack is created the stack configuration is merged with the
            configuration for this environment.
        """
      , "chosen_task": "to_be_filled_in"
      , "chosen_stack": "to_be_filled_in"
      , "extra_imports": "to_be_filled_in"
      , "configuration": "to_be_filled_in"
      , "no_assume_role": "to_be_filled_in"
      , "chosen_artifact": "to_be_filled_in"
      }

    def get_variable(self, artifact):
        try:
            val = self.configuration.root()
            env_objs = []
            for part in artifact.split(','):
                val = val[part]
                if hasattr(val, "env"):
                    env_objs.append(val.env)
                if hasattr(val, "build_env"):
                    env_objs.append(val.build_env)

            if isinstance(val, stack_objs.StaticVariable):
                val = val.resolve()
            elif isinstance(val, stack_objs.DynamicVariable):
                self.set_credentials()
                val = val.resolve()
            if isinstance(val, MergedOptions):
                val = val.as_dict()

            if env_objs and isinstance(val, six.string_types):
                envs = dict(chain.from_iterable([(env.env_name, env) for env in env_obj] for env_obj in env_objs))
                wanted = []
                class Formatter(string.Formatter):
                    def get_field(self, key, args, kwargs, format_spec=None):
                        if key not in envs:
                            raise BadOptionFormat("Couldn't find an environment specification", wanted=key, available=list(envs.keys()))
                        wanted.append(envs[key])

                        if envs[key].missing:
                            return '', key
                        else:
                            return envs[key].pair[1], key
                val = Formatter().format(val)
                missing = [env.env_name for env in wanted if env.missing]
                if any(missing):
                    raise BadOption("Some environment variables aren't in the current environment", missing=missing)

            return val
        except KeyError:
            raise MissingVariable(wanted=artifact)

