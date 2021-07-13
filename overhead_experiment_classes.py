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
        return "entity50kb"


@stateflow.stateflow
class Entity5MB:
    def __init__(self):
        self.data = bytearray([1] * 5000000)

    def execute(self):
        pass

    def __key__(self):
        return "entity50kb"


@stateflow.stateflow
class Entity50MB:
    def __init__(self):
        self.data = bytearray([1] * 50000000)

    def execute(self):
        pass

    def __key__(self):
        return "entity50kb"
