from stateflow import StateFlow, stateflow
from example.shop import User, Item
from runtime.beam_runtime import BeamRuntime

stateflow(User)
stateflow(Item)

flow = StateFlow(runtime=BeamRuntime())
flow.run()
