from bespin.errors import StackDepCycle

class Layers(object):
    """
    Used to order the creation of many stacks.

    Usage::

        layers = Layers({"stack1": stack1, "stack2": "stack2, "stack3": stack3, "stack4": stack4})
        layers.add_to_layers("stack3")
        for layer in layers.layered:
            # might get something like
            # [("stack3", stack4), ("stack2", stack2)]
            # [("stack3", stack3)]

    When we create the layers, it will do a depth first addition of all dependencies
    and only add a stack to a layer that occurs after all it's dependencies.

    Cyclic dependencies will be complained about.
    """
    def __init__(self, stacks, all_stacks=None):
        self.stacks = stacks
        self.all_stacks = all_stacks
        if self.all_stacks is None:
            self.all_stacks = stacks

        self.accounted = {}
        self._layered = []

    def reset(self):
        """Make a clean slate (initialize layered and accounted on the instance)"""
        self.accounted = {}
        self._layered = []

    @property
    def layered(self):
        """Yield list of [[(name, stack), ...], [(name, stack), ...], ...]"""
        result = []
        for layer in self._layered:
            nxt = []
            for name in layer:
                nxt.append((name, self.all_stacks[name]))
            result.append(nxt)
        return result

    def add_all_to_layers(self):
        """Add all the stacks to layered"""
        for stack in sorted(self.stacks):
            self.add_to_layers(stack)

    def add_to_layers(self, name, chain=None):
        layered = self._layered

        if name not in self.accounted:
            self.accounted[name] = True
        else:
            return

        if chain is None:
            chain = []
        chain = chain + [name]

        for dependency in sorted(self.all_stacks[name].dependencies(self.all_stacks)):
            dep_chain = list(chain)
            if dependency in chain:
                dep_chain.append(dependency)
                raise StackDepCycle(chain=dep_chain)
            self.add_to_layers(dependency, dep_chain)

        layer = 0
        for dependency in self.all_stacks[name].dependencies(self.all_stacks):
            for index, deps in enumerate(layered):
                if dependency in deps:
                    if layer <= index:
                        layer = index + 1
                    continue

        if len(layered) == layer:
            layered.append([])
        layered[layer].append(name)

