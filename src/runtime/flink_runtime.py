from src.runtime.runtime import Runtime
from pyflink.datastream import (
    ProcessFunction,
    RuntimeContext,
    MapFunction,
    StreamExecutionEnvironment,
    DataStream,
)
from pyflink.datastream.connectors import (
    FlinkKafkaConsumer,
    FlinkKafkaProducer,
)
from pyflink.common.serialization import SimpleStringSchema
from pyflink.datastream.state import ValueStateDescriptor, ValueState
from pyflink.common.typeinfo import Types
from src.dataflow.stateful_operator import StatefulOperator, Event
from src.dataflow.dataflow import (
    IngressRouter,
    Route,
    EgressRouter,
    Dataflow,
    RouteDirection,
)
from src.serialization.json_serde import SerDe, JsonSerializer
from typing import Tuple, List
import uuid


class FlinkIngressRouter(MapFunction):
    def __init__(self, router: IngressRouter):
        self.router = router

    def map(self, value) -> Route:
        route = self.router.parse_and_route(value[1])
        return route


class FlinkEgressRouter(MapFunction):
    def __init__(self, router: EgressRouter):
        self.router = router

    def map(self, value: Tuple[str, Event]) -> Route:
        route = self.router.route_and_serialize(value[1])
        return route


class FlinkInitOperator(MapFunction):
    def __init__(self, operator: StatefulOperator):
        self.operator: StatefulOperator = operator

    def map(self, value) -> Tuple[str, Event]:
        return_event = self.operator.handle_create(value[1])
        yield return_event.event_id, return_event


class FlinkOperator(ProcessFunction):
    def __init__(self, operator: StatefulOperator):
        self.state: ValueState = None
        self.operator: StatefulOperator = operator

    def open(self, runtime_context: RuntimeContext):
        descriptor = ValueStateDescriptor("state", Types.BYTE())
        self.state: ValueState = runtime_context.get_state(descriptor)

    def process_element(self, value, ctx: ProcessFunction.Context) -> Event:
        return_event, updated_state = self.operator.handle(value[1], self.state.value())

        if updated_state is not None:
            self.state.update(updated_state)

        yield return_event


class FlinkRuntime(Runtime):
    def __init__(self, dataflow: Dataflow, serializer: SerDe = JsonSerializer()):
        super().__init__()
        self.dataflow = dataflow
        self.serializer = serializer
        self.env: StreamExecutionEnvironment = (
            StreamExecutionEnvironment.get_execution_environment()
        )

        self.operators = self.dataflow.operators

    def _setup_kafka_client(self) -> FlinkKafkaConsumer:
        return FlinkKafkaConsumer(
            ["client_request", "internal"],
            SimpleStringSchema(),
            {
                "bootstrap.servers": "localhost:9092",
                "auto.offset.reset": "latest",
                "group.id": str(uuid.uuid4()),
            },
        )

    def _setup_kafka_producer(self, topic: str) -> FlinkKafkaProducer:
        return FlinkKafkaProducer(
            topic, SimpleStringSchema(), {"bootstraps.servers": "localhost:9092"}
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
            EgressRouter(self.serializer)
        )

        # Reading all Kafka messages here
        routed_kafka_consumption: DataStream[Route] = self.env.from_source(
            kafka_consumer
        ).map(ingress_router, Route)

        final_operator_streams: List[DataStream] = []

        for operator in self.operators:
            op_name: str = operator.operator.function_type.get_full_name()
            stateful_operator: FlinkOperator = FlinkOperator(operator)
            init_operator: FlinkInitOperator = FlinkInitOperator(operator)

            operator_stream = routed_kafka_consumption.filter(
                lambda r: r.route_direction is RouteDirection.CLIENT
                and r.route == op_name
            ).map(lambda r: (r.key, r.value))

            init_stream = (
                operator_stream.filter(lambda r: r[0] is None)
                .map(init_operator)
                .key_by(lambda x: x[0])
            )

            stateful_operator_steam = operator_stream.filter(
                lambda r: r[0] is not None
            ).key_by(lambda x: x[0])

            final_operator_stream = init_stream.union(stateful_operator_steam).process(
                stateful_operator
            )

            final_operator_streams.append(final_operator_stream)

        egress_stream: DataStream[Route] = (
            routed_kafka_consumption.filter(
                lambda r: r.route_direction is RouteDirection.EGRESS
            )
            .map(lambda r: r.value)
            .union(*final_operator_streams)
        ).map(egress_router)

        # Reply output
        egress_stream.filter(lambda r: r.route_direction is RouteDirection.CLIENT).map(
            lambda r: (r.key, r.value)
        ).add_sink(kafka_producer_reply)

        # Internal output
        egress_stream.filter(
            lambda r: r.route_direction is RouteDirection.INTERNAL
        ).map(lambda r: (r.key, r.value)).add_sink(kafka_producer_reply)

    def run(self):
        self.env.execute("Stateflow Runtime")
