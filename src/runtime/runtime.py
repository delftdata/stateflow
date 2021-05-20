from src.dataflow.dataflow import Dataflow


class Runtime:
    def __init__(self):
        raise NotImplementedError()

    def _setup_pipeline(self):
        raise NotImplementedError()

    def run(self):
        raise NotImplementedError()
