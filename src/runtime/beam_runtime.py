from apache_beam import DoFn
from apache_beam.coders import BytesCoder
from apache_beam.transforms.userstate import ReadModifyWriteStateSpec
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from beam_nuggets.io import kafkaio

from src.dataflow import StatefulOperator
from typing import List, Tuple, Any, Union
from src.serialization.json_serde import JsonSerializer, SerDe
from src.runtime.runtime import Runtime
from src.dataflow import Dataflow, Ingress, Arguments
from src.dataflow import (
    State,
    Event,
    EventType,
    Operator,
    FunctionAddress,
    FunctionType,
)
from apache_beam import pvalue
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.runners.interactive.display import pipeline_graph_renderer


class IngressBeamRouter(DoFn):
    def __init__(self, operators: List[Operator], serializer: SerDe):
        self.operators: List[Operator] = operators
        self.serializer = serializer

        self.outputs = set()

        for operator in self.operators:
            if isinstance(operator, StatefulOperator):
                name: str = operator.function_type.get_full_name()

                self.outputs.add(f"{name}")

    def process(self, element: Tuple[bytes, bytes]) -> Union[Tuple[str, Any], Any]:
        event: Event = self.serializer.deserialize_event(element[1])
        event_type: str = event.event_type
        route_name: str = f"{event.fun_address.function_type.get_full_name()}"

        if not isinstance(event_type, EventType.Request):
            yield (
                event.event_id,
                event.copy(
                    event_type=EventType.Reply.FailedInvocation,
                    payload={
                        "error_message": "This IngressRouter only supports event requests."
                    },
                ),
            )
        elif route_name not in self.outputs:
            yield (
                event.event_id,
                event.copy(
                    event_type=EventType.Reply.FailedInvocation,
                    payload={"error_message": "This event could not be routed."},
                ),
            )

        # if the key is available, then we set that as key otherwise we set the event_id.
        elif event.fun_address.key:
            yield pvalue.TaggedOutput(route_name, (event.fun_address.key, event))
        else:
            yield pvalue.TaggedOutput(route_name, (event.event_id, event))


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

    def __init__(self, operator: StatefulOperator, serializer: SerDe):
        self.operator = operator
        self.serializer = serializer

    @beam.typehints.with_input_types(Tuple[str, Any])
    def process(
        self, element: Tuple[str, Any], operator_state=DoFn.StateParam(STATE_SPEC)
    ) -> Tuple[str, Any]:
        # print(f"Executing event for {element[0]} {element[1].event_type}")
        # print(f"{operator_state.read()}")
        # Execute event.
        # print(element)
        return_event, updated_state = self.operator.handle(
            element[1], operator_state.read()
        )

        # Update state.
        if updated_state is not None:
            operator_state.write(updated_state)

        # print(
        #      f"Sending  {return_event.event_id} {self.serializer.serialize_event(return_event)}"
        #  )
        yield (return_event.event_id, self.serializer.serialize_event(return_event))


class BeamRuntime(Runtime):
    def __init__(self, dataflow: Dataflow, serializer: SerDe = JsonSerializer()):
        self.init_operators: List[BeamInitOperator] = []
        self.operators: List[BeamOperator] = []

        self.serializer = serializer
        self.ingress_router = IngressBeamRouter(dataflow.operators, JsonSerializer())

        for operator in dataflow.operators:
            operator.meta_wrapper = None  # We set this meta wrapper to None, we don't need it in the runtime.
            self.init_operators.append(BeamInitOperator(operator))
            self.operators.append(BeamOperator(operator, self.serializer))

    def run(self):
        print("Running Beam pipeline!")

        opt = PipelineOptions(["--runner=FlinkRunner", "--environment_type=LOOPBACK"])

        with beam.Pipeline(options=PipelineOptions(streaming=True)) as pipeline:

            kafka_client = kafkaio.KafkaConsume(
                consumer_config={
                    "bootstrap_servers": "localhost:9092",
                    "auto_offset_reset": "earliest",
                    "group_id": "noww",
                    "topic": "client_request",
                },
                value_decoder=bytes,
            )

            kafka_producer = kafkaio.KafkaProduce(
                servers="localhost:9092",
                topic="client_reply",
            )

            # Read from Kafka and route
            input_and_router = (
                pipeline
                | "kafka-input" >> kafka_client
                | beam.ParDo(self.ingress_router).with_outputs(
                    *list(self.ingress_router.outputs), main="ingress_router_output"
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
                    | f"{name}_stateful" >> beam.ParDo(operator)
                    | f"{name}_kafka" >> kafka_producer
                )

            input_and_router[
                "ingress_router_output"
            ] | "direct_output_kafka" >> kafka_producer

            pipeline.run()
