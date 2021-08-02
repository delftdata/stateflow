from overhead_experiment_classes import stateflow
from stateflow.runtime.flink.pyflink import FlinkRuntime
from stateflow.serialization.pickle_serializer import PickleSerializer
from stateflow.runtime.flink.statefun import StatefunRuntime, web

# Initialize stateflow
flow = stateflow.init()

runtime: StatefunRuntime = FlinkRuntime(flow, serializer=PickleSerializer())
runtime.run()
# app = runtime.get_app()
#
# if __name__ == "__main__":
#     web.run_app(app, port=8000)
