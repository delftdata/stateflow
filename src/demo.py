from stateflow import StateFlow
from runtime.beam_runtime import BeamRuntime

flow = StateFlow(runtime=BeamRuntime())
flow.run()
