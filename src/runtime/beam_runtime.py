import uuid

from apache_beam import DoFn
from apache_beam.coders import BytesCoder
from apache_beam.transforms.userstate import ReadModifyWriteStateSpec
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from beam_nuggets.io import kafkaio

from src.runtime.KafkaConsumer import KafkaConsume
from src.dataflow.stateful_operator import StatefulOperator, Operator
from typing import List, Tuple, Any, Union, ByteString
from src.serialization.json_serde import JsonSerializer, SerDe
from src.runtime.runtime import Runtime
from src.dataflow.dataflow import (
    Dataflow,
    IngressRouter,
    Route,
    RouteDirection,
    EgressRouter,
)
from src.dataflow.event import Event, EventType
from apache_beam import pvalue
from apache_beam.testing.test_pipeline import TestPipeline


class IngressBeamRouter(DoFn):
    def __init__(
        self, operators: List[Operator], router: IngressRouter, egress: EgressRouter
    ):
        self.operators: List[Operator] = operators
        self.router: IngressRouter = router
        self.egress: EgressRouter = egress
        self.outputs = set()

        for operator in self.operators:
            if isinstance(operator, StatefulOperator):
                name: str = operator.function_type.get_full_name()
                self.outputs.add(f"{name}")

        self.outputs.add("client")
        self.outputs.add("internal")

    def process(self, element: Tuple[bytes, bytes]) -> Union[Tuple[str, Any], Any]:
        route: Route = self.router.parse_and_route(element[1])

        if route.direction == RouteDirection.EGRESS:
            egress_route = self.egress.route_and_serialize(route.value)
            if egress_route.direction == RouteDirection.CLIENT:
                yield pvalue.TaggedOutput("client", (route.key, egress_route.value))
            elif egress_route.direction == RouteDirection.INTERNAL:
                yield pvalue.TaggedOutput("internal", (route.key, egress_route.value))
        elif route.direction == RouteDirection.INTERNAL:
            yield pvalue.TaggedOutput(route.route_name, (route.key, route.value))
        else:
            raise AttributeError(f"Unknown route direction {route.direction}.")


class BeamInitOperator(DoFn):
    def __init__(self, operator: StatefulOperator):
        self.operator = operator

    @beam.typehints.with_input_types(Tuple[str, Any])
    def process(self, element: Tuple[str, Any]) -> Tuple[str, Any]:
        if element[1].event_type != EventType.Request.InitClass:
            yield element[0], element[1]
        else:
            return_event = self.operator.handle_create(element[1])
            print(f"{return_event} with key {return_event.fun_address.key}")
            yield return_event.fun_address.key, return_event


class BeamOperator(DoFn):
    STATE_SPEC = ReadModifyWriteStateSpec("state", BytesCoder())

    def __init__(
        self, operator: StatefulOperator, serializer: SerDe, router: EgressRouter
    ):
        self.operator = operator
        self.serializer = serializer
        self.router = router

    @beam.typehints.with_input_types(Tuple[str, Any])
    def process(
        self, element: Tuple[str, Any], operator_state=DoFn.StateParam(STATE_SPEC)
    ) -> Tuple[str, Any]:
        return_event, updated_state = self.operator.handle(
            element[1], operator_state.read()
        )

        # Update state.
        if updated_state is not None:
            operator_state.write(updated_state)

        route = self.router.route_and_serialize(return_event)

        if route.direction == RouteDirection.CLIENT:
            yield pvalue.TaggedOutput("client", (route.key, route.value))
        elif route.direction == RouteDirection.INTERNAL:
            yield pvalue.TaggedOutput("internal", (route.key, route.value))
        else:
            raise AttributeError(f"Unknown route direction {route.direction}.")


class BeamRuntime(Runtime):
    def __init__(
        self,
        dataflow: Dataflow,
        serializer: SerDe = JsonSerializer(),
        test_mode=False,
        timeout=-1,
    ):
        self.init_operators: List[BeamInitOperator] = []
        self.operators: List[BeamOperator] = []

        self.serializer = serializer
        self.egress_router = EgressRouter(serializer)
        self.ingress_router = IngressBeamRouter(
            dataflow.operators, IngressRouter(serializer), self.egress_router
        )

        self.pipeline: beam.Pipeline = None

        # Test-related variables.
        # If enabled, we keep track of the output collections.
        # We can use this to verify (and test) the outputs of the pipeline.
        self.test_mode = test_mode
        self.test_output = {}
        self.timeout = timeout

        for operator in dataflow.operators:
            operator.meta_wrapper = None  # We set this meta wrapper to None, we don't need it in the runtime.
            self.init_operators.append(BeamInitOperator(operator))
            self.operators.append(
                BeamOperator(operator, self.serializer, self.egress_router)
            )

    def _setup_kafka_client(self) -> KafkaConsume:
        return KafkaConsume(
            consumer_config={
                "bootstrap.servers": "localhost:9092",
                "auto.offset.reset": "latest",
                "group.id": str(uuid.uuid4()),
                "topic": ["client_request", "internal"],
            },
            value_decoder=bytes,
            timeout=self.timeout,
        )

    def _setup_kafka_producer(self, topic: str) -> kafkaio.KafkaProduce:
        return kafkaio.KafkaProduce(
            servers="localhost:9092",
            topic=topic,
        )

    def _setup_pipeline(self):
        if self.test_mode:
            pipeline = beam.testing.test_pipeline.TestPipeline(blocking=False)
        else:
            pipeline = beam.Pipeline(options=PipelineOptions())

        # Setup KafkaIO.
        kafka_client = self._setup_kafka_client()
        kafka_producer = self._setup_kafka_producer("client_reply")
        kafka_producer_internal = self._setup_kafka_producer("internal")

        # Read from Kafka and route
        input_and_router = (
            pipeline
            | "kafka-input" >> kafka_client
            | beam.ParDo(self.ingress_router).with_outputs(
                *list(self.ingress_router.outputs)
            )
        )

        for operator, init_operator in zip(self.operators, self.init_operators):
            name = operator.operator.function_type.get_full_name()

            init_class = input_and_router[
                f"{init_operator.operator.function_type.get_full_name()}"
            ]

            operator_pipeline = (
                init_class
                | f"{name}_init" >> beam.ParDo(init_operator)
                | f"{name}_stateful"
                >> beam.ParDo(operator).with_outputs("client", "internal")
            )

            external_output = (
                operator_pipeline["client"] | f"{name}_kafka" >> kafka_producer
            )
            internal_output = (
                operator_pipeline["internal"]
                | f"{name}_kafka_internal" >> kafka_producer_internal
            )

            if self.test_mode:
                self.test_output[f"{name}_external"] = external_output
                self.test_output[f"{name}_internal"] = internal_output

        input_and_router[
            "internal"
        ] | "egress_internal_router" >> kafka_producer_internal
        input_and_router["client"] | "egress_client_router" >> kafka_producer

        self.pipeline = pipeline

    def run(self):
        print("Running Beam pipeline!")
        if not self.pipeline:
            self._setup_pipeline()

        if not self.test_mode:
            self.pipeline.run().wait_until_finish()
        else:
            result = self.pipeline.run()
            result.wait_until_finish()
