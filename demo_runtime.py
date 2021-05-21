from demo_common import stateflow
from src.runtime.beam_runtime import BeamRuntime, Runtime
from src.runtime.flink_runtime import FlinkRuntime

# Initialize stateflow
flow = stateflow.init()

runtime: Runtime = FlinkRuntime(flow)
runtime.run()
