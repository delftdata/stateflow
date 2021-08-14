from demo_common import stateflow
from stateflow.runtime.beam_runtime import BeamRuntime, Runtime
from stateflow.serialization.pickle_serializer import PickleSerializer

# Initialize stateflow
flow = stateflow.init()

runtime: BeamRuntime = BeamRuntime(flow, serializer=PickleSerializer())
runtime.run()
