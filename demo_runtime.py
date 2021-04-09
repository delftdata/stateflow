from demo_common import stateflow
from src.runtime.beam_runtime import BeamRuntime, Runtime

# Initialize stateflow
flow = stateflow.init()

runtime: Runtime = BeamRuntime(flow)
runtime.run()
