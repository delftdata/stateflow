class Runtime:
    def __init__(self):
        pass

    def _setup_pipeline(self):
        raise NotImplementedError()

    def run(self, async_execution=False):
        raise NotImplementedError()
