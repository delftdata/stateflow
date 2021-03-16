from pyflink.common.typeinfo import Types
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.functions import KeyedProcessFunction

from runtime.runtime import Runtime
from dataflow import Dataflow


class FlinkStatefulOperator(KeyedProcessFunction):
    def process_element(self, value, ctx: "KeyedProcessFunction.Context"):
        print(f"Processing {value}")
        print(f"{ctx}")


class FlinkRuntime(Runtime):
    def transform(self, dataflow: Dataflow):
        pass

    def run(self):
        print("Running Flink Runtime!")
        env = StreamExecutionEnvironment.get_execution_environment()
        env.set_parallelism(1)

        ds = env.from_collection(
            collection=[(1, "bbb")],
            type_info=Types.ROW([Types.INT(), Types.STRING()]),
        )

        ds.process(FlinkStatefulOperator())
        ds.print()
        env.execute("simple_job")
