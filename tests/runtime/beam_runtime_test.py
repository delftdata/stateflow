from tests.common.common_classes import User, Item, stateflow
from src.runtime.beam_runtime import BeamRuntime, Runtime
from apache_beam.testing.test_stream import TestStream
import apache_beam as beam


class TestBeamRuntime:
    def return_test_stream(self):
        return TestStream()

    def identity(self, *args, **kwargs):
        return beam.Map(lambda x: x)

    def setup_beam_runtime(self):
        runtime: BeamRuntime = BeamRuntime(stateflow.init())
        runtime._setup_kafka_client = self.return_test_stream
        runtime._setup_kafka_producer = self.identity

        runtime.run()

    def test_runtime(self):
        self.setup_beam_runtime()
        pass
