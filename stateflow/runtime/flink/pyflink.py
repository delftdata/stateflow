from stateflow.runtime.runtime import Runtime
from pyflink.datastream import (
    RuntimeContext,
    MapFunction,
    StreamExecutionEnvironment,
    DataStream,
)

from pyflink.datastream.connectors import (
    FlinkKafkaConsumer,
    FlinkKafkaProducer,
)
from typing import Dict
from pyflink.common import Configuration
from pyflink.util.java_utils import get_j_env_configuration, get_gateway

from pyflink.common.serialization import (
    SerializationSchema,
    DeserializationSchema,
)
from pyflink.datastream.state import ValueStateDescriptor, ValueState
from pyflink.datastream.data_stream import KeyedProcessFunction, ProcessFunction
from pyflink.common.typeinfo import Types
from stateflow.dataflow.stateful_operator import StatefulOperator, Event
from stateflow.dataflow.dataflow import (
    IngressRouter,
    Route,
    EgressRouter,
    Dataflow,
    RouteDirection,
)
from stateflow.serialization.json_serde import SerDe, JsonSerializer
from typing import List
import uuid


class ByteSerializer(SerializationSchema, DeserializationSchema):
    def __init__(self):
        gate_way = get_gateway()

        j_byte_string_schema = gate_way.jvm.nl.tudelft.stateflow.KafkaBytesSerializer()

        SerializationSchema.__init__(self, j_serialization_schema=j_byte_string_schema)
        DeserializationSchema.__init__(
            self, j_deserialization_schema=j_byte_string_schema
        )


class FlinkIngressRouter(MapFunction):
    def __init__(self, router: IngressRouter):
        self.router = router

    def map(self, value) -> Route:
        route = self.router.parse_and_route(value)
        return route


class FlinkEgressRouter(MapFunction):
    def __init__(self, router: EgressRouter):
        self.router = router

    def map(self, value: Event) -> Route:
        route: Route = self.router.route_and_serialize(value)
        return route


class FlinkInitOperator(ProcessFunction):
    def __init__(self, operator: StatefulOperator):
        self.operator: StatefulOperator = operator

    def process_element(self, value, ctx: "ProcessFunction.Context"):
        import logging

        return_event = self.operator.handle_create(value[1])
        yield return_event.fun_address.key, return_event


class FlinkOperator(KeyedProcessFunction):
    def __init__(self, operator: StatefulOperator):
        self.state: ValueState = None
        self.operator: StatefulOperator = operator

    def open(self, runtime_context: RuntimeContext):
        descriptor = ValueStateDescriptor("state", Types.BYTE())
        self.state: ValueState = runtime_context.get_state(descriptor)

    def process_element(self, value, ctx: KeyedProcessFunction.Context) -> Event:
        original_state = self.state.value()
        return_event, updated_state = self.operator.handle(value[1], original_state)

        if updated_state is not original_state:
            self.state.update(updated_state)

        yield return_event


class FlinkRuntime(Runtime):
    def __init__(
        self,
        dataflow: Dataflow,
        serializer: SerDe = JsonSerializer(),
        bundle_time: int = 1,
        bundle_size: int = 5,
        consumer_config: Dict = {
            "bootstrap.servers": "localhost:9092",
            "auto.offset.reset": "latest",
            "group.id": str(uuid.uuid4()),
        },
        producer_config: Dict = {"bootstrap.servers": "localhost:9092"},
    ):
        super().__init__()
        self.dataflow = dataflow
        self.serializer = serializer
        self.env: StreamExecutionEnvironment = (
            StreamExecutionEnvironment.get_execution_environment()
        )

        self.operators = self.dataflow.operators
        self.pipeline_initialized: bool = False
        self.consumer_config = consumer_config
        self.producer_config = producer_config

        config = Configuration(
            j_configuration=get_j_env_configuration(
                self.env._j_stream_execution_environment
            )
        )

        config.set_integer("python.fn-execution.bundle.time", bundle_time)
        config.set_integer("python.fn-execution.bundle.size", bundle_size)

        import os

        jar_path = os.path.abspath("bin/flink-sql-connector-kafka_2.11-1.13.0.jar")
        jar_path_serial = os.path.abspath("bin/flink-kafka-1.8.jar")
        self.env.add_jars(f"file://{jar_path}")
        self.env.add_jars(f"file://{jar_path_serial}")

    def _setup_kafka_client(self) -> FlinkKafkaConsumer:
        return FlinkKafkaConsumer(
            ["client_request", "internal"],
            ByteSerializer(),
            self.consumer_config,
        )

    def _setup_kafka_producer(self, topic: str) -> FlinkKafkaProducer:
        return FlinkKafkaProducer(
            topic,
            ByteSerializer(),
            self.producer_config,
        )

    def _setup_pipeline(self):
        # Setup all Kafka communication.
        kafka_consumer: FlinkKafkaConsumer = self._setup_kafka_client()
        kafka_producer_reply: FlinkKafkaProducer = self._setup_kafka_producer(
            "client_reply"
        )
        kafka_producer_internal: FlinkKafkaProducer = self._setup_kafka_producer(
            "internal"
        )

        # Routers
        ingress_router: FlinkIngressRouter = FlinkIngressRouter(
            IngressRouter(self.serializer)
        )
        egress_router: FlinkEgressRouter = FlinkEgressRouter(
            EgressRouter(self.serializer, False)
        )

        # Reading all Kafka messages here
        routed_kafka_consumption: DataStream[Route] = (
            self.env.add_source(kafka_consumer)
            .map(ingress_router)
            .name("Route-Incoming-Events")
        )

        final_operator_streams: List[DataStream] = []

        for operator in self.operators:
            op_name: str = operator.function_type.get_full_name()
            stateful_operator: FlinkOperator = FlinkOperator(operator)
            init_operator: FlinkInitOperator = FlinkInitOperator(operator)

            operator_stream = (
                routed_kafka_consumption.filter(
                    lambda r: r.direction is RouteDirection.INTERNAL
                    and r.route_name == op_name
                )
                .name(f"Filter-On-{operator.function_type.name}")
                .map(lambda r: (r.key, r.value))
            )

            init_stream = (
                operator_stream.filter(lambda r: r[0] is None)
                .name(f"Filter-Init-{operator.function_type.name}")
                .process(init_operator)
                .name(f"Init-{operator.function_type.name}")
            )

            stateful_operator_stream = operator_stream.filter(
                lambda r: r[0] is not None,
            ).name(f"Filter-Stateful-{operator.function_type.name}")

            final_operator_stream = (
                stateful_operator_stream.union(init_stream)
                .key_by(lambda x: x[0])
                .process(stateful_operator)
                .name(f"Process-Stateful-{operator.function_type.name}")
            )

            final_operator_streams.append(final_operator_stream)

        egress_stream: DataStream[Route] = (
            (
                routed_kafka_consumption.filter(
                    lambda r: r.direction is RouteDirection.EGRESS
                )
                .map(lambda r: r.value)
                .union(*final_operator_streams)
            )
            .map(egress_router)
            .name(f"Map-Egress")
        )

        # Reply output
        egress_stream.filter(lambda r: r.direction is RouteDirection.CLIENT).map(
            lambda r: r.value
        ).name(f"Kafka-To-Client").add_sink(kafka_producer_reply)

        # Internal output
        egress_stream.filter(lambda r: r.direction is RouteDirection.INTERNAL).map(
            lambda r: r.value
        ).name(f"Kafka-To-Internal").add_sink(kafka_producer_internal)

        self.pipeline_initialized = True

    def run(self, async_execution=False):
        print("Now running Flink runtime!", flush=True)
        if not self.pipeline_initialized:
            self._setup_pipeline()

        if async_execution:
            self.env.execute_async("Stateflow Runtime")
        else:
            self.env.execute("Stateflow Runtime")
