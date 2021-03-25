from runtime.runtime import Runtime


def stateflow(definition):
    pass


class StateFlow:
    def __init__(self, runtime: Runtime):
        self.runtime = runtime

    def run(self):
        self.runtime.run()
