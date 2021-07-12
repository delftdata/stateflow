from demo_common import stateflow
from stateflow.runtime.beam_runtime import BeamRuntime, Runtime
from stateflow.serialization.pickle_serializer import PickleSerializer
from stateflow.runtime.flink.statefun import StatefunRuntime, web

# Initialize stateflow
flow = stateflow.init()

runtime: StatefunRuntime = StatefunRuntime(flow, serializer=PickleSerializer())
app = runtime.get_app()

if __name__ == "__main__":
    web.run_app(app, port=8000)
