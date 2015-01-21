from bespin.errors import BadOption, BadOptionFormat, MissingVariable
from bespin.option_spec import stack_objs

from input_algorithms.dictobj import dictobj
from option_merge import MergedOptions
from itertools import chain
import string
import six

class Bespin(dictobj):
    fields = [
          "dry_run", "assume_role", "flat", "config", "chosen_stack", "no_assume_role", "extra_imports"
        , "region", "environment", "chosen_artifact", "chosen_task", "extra", "interactive", "configuration"
        ]

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

