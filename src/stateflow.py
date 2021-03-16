from runtime.runtime import Runtime


class StateFlow:
    def __init__(self, runtime: Runtime):
        self.runtime = runtime

    def run(self):
        self.runtime.run()
