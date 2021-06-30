from demo_common import stateflow
from stateflow.runtime.beam_runtime import BeamRuntime, Runtime
from stateflow.runtime.flink_runtime import FlinkRuntime
from stateflow.serialization.pickle_serializer import PickleSerializer

# Initialize stateflow
flow = stateflow.init()

runtime: Runtime = BeamRuntime(flow, serializer=PickleSerializer())
runtime.run()
