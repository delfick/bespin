from textwrap import dedent

default_tasks = None
available_tasks = None

class a_task(object):
    def __init__(self, **kwargs):
        raise DeprecationWarning(dedent("""
            the @bespin.tasks.a_task decorator has been deprecated in favour of @bespin.actions.an_action

            This new decorator is the same except it has no needs_stacks option.

            The signature of the actions themselves has also changed.

            It is no longer (collector, configuration, stacks, stack, artifact, tasks)

            It is now (collector, stack, artifact, tasks)

            configuration can be found at collector.configuration

            stacks can be found at collector.configuration["stacks"]
        """))
