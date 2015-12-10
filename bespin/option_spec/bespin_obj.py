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
      , "config": "Holds a file object to the specified Bespin configuration file"
      , "extra": "Holds extra arguments after a -- when executed from the command line"
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
      , "chosen_task": "The task to execute"
      , "chosen_stack": "The stack to pass into the task"
      , "extra_imports": "Any extra files to import before searching for the chosen task"
      , "configuration": "The root of the configuration"
      , "no_assume_role": "Boolean saying if we should assume role or not"
      , "chosen_artifact": "The value of the --artifact option. This is used to mean several things via the tasks"
      }

    def get_variable(self, artifact):
        try:
            val = self.configuration.root()
            env_objs = []
            for part in artifact.split(','):
                val = val[part]
                if callable(val):
                    val = val()
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

