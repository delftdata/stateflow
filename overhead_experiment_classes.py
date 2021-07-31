import stateflow


@stateflow.stateflow
class Entity50KB:
    def __init__(self):
        self.data = bytearray([1] * 50000)

    def execute(self):
        pass

    def __key__(self):
        return "entity50kb"


@stateflow.stateflow
class Entity500KB:
    def __init__(self):
        self.data = bytearray([1] * 500000)

    def execute(self):
        pass

    def __key__(self):
        return "entity500kb"


@stateflow.stateflow
class Entity5MB:
    def __init__(self):
        self.data = bytearray([1] * 5000000)

    def execute(self):
        pass

    def __key__(self):
        return "entity5mb"


@stateflow.stateflow
class Entity50MB:
    def __init__(self):
        self.data = bytearray([1] * 50000000)

    def execute(self):
        pass

    def __key__(self):
        return "entity50mb"


@stateflow.stateflow
class EntityExecutionGraph10:
    def __init__(self):
        self.data = bytearray([1] * 50000000)

    def execute(self, other: "EntityExecutionGraph10"):
        # Adding 'other' parameters,
        # triggers the function to be split.
        x = 1

        if True:
            if True:
                ...
                return x

    def __key__(self):
        return "entityexecutiongraph10"
