from demo_common import stateflow
from src.runtime.beam_runtime import BeamRuntime, Runtime
from src.runtime.flink_runtime import FlinkRuntime
from src.serialization.pickle_serializer import PickleSerializer

# Initialize stateflow
flow = stateflow.init()

runtime: Runtime = BeamRuntime(flow, serializer=PickleSerializer())
runtime.run()
