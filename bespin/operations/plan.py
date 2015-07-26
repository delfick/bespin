from bespin.errors import BadOption, MissingPlan

from input_algorithms.spec_base import NotSpecified

class Plan(object):
    @classmethod
    def find_stacks(kls, configuration, stacks, plan):
        if plan in (None, NotSpecified):
            raise BadOption("Please specify a plan", available=list(configuration["plans"].keys()))

        if plan not in configuration["plans"]:
            raise MissingPlan(wanted=plan, available=configuration["plans"].keys())

        missing = []

        for stack in configuration["plans"][plan]:
            if stack not in stacks:
                missing.append(stack)

        if missing:
            raise BadOption("Some stacks in the plan don't exist", missing=missing, available=stacks.keys())

        for stack in configuration["plans"][plan]:
            yield stack

