import uuid

from apache_beam import DoFn
from apache_beam.coders import BytesCoder
from apache_beam.transforms.userstate import ReadModifyWriteStateSpec
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from beam_nuggets.io import kafkaio

from src.runtime.KafkaConsumer import KafkaConsume
from src.dataflow.stateful_operator import StatefulOperator, Operator
from typing import List, Tuple, Any, Union
from src.serialization.json_serde import JsonSerializer, SerDe
from src.runtime.runtime import Runtime
from src.dataflow.dataflow import Dataflow
from src.dataflow.state import State
from src.dataflow.event import Event, EventType, EventFlowNode
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
        elif event.event_type == EventType.Request.EventFlow:
            flow = event.payload["flow"]
            current_id = event.payload["current_flow"]

            current_node = flow[str(current_id)]["node"]

            if current_node.typ == EventFlowNode.RETURN:
                yield (
                    event.event_id,
                    self.serializer.serialize_event(
                        event.copy(
                            event_type=EventType.Reply.SuccessfulInvocation,
                            payload={
                                "return_results": list(current_node.output.values())
                            },
                        )
                    ),
                )
            elif current_node.typ == EventFlowNode.REQUEST_STATE:
                key = current_node.input["key"]
                yield pvalue.TaggedOutput(
                    current_node.fun_type.get_full_name(), (key, event)
                )
            elif current_node.typ == EventFlowNode.INVOKE_SPLIT_FUN:
                yield pvalue.TaggedOutput(
                    current_node.fun_type.get_full_name(),
                    (event.fun_address.key, event),
                )
            elif current_node.typ == EventFlowNode.INVOKE_EXTERNAL:
                yield pvalue.TaggedOutput(
                    current_node.fun_type.get_full_name(), (current_node.key, event)
                )

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
        if return_event.event_type == EventType.Request.EventFlow:
            yield pvalue.TaggedOutput(
                "internal",
                (return_event.event_id, self.serializer.serialize_event(return_event)),
            )
        else:
            yield (return_event.event_id, self.serializer.serialize_event(return_event))


class BeamRuntime(Runtime):
    def __init__(
        self, dataflow: Dataflow, serializer: SerDe = JsonSerializer(), test_mode=False
    ):
        self.init_operators: List[BeamInitOperator] = []
        self.operators: List[BeamOperator] = []

        self.serializer = serializer
        self.ingress_router = IngressBeamRouter(dataflow.operators, JsonSerializer())

        self.pipeline: beam.Pipeline = None

        # Test-related variables.
        # If enabled, we keep track of the output collections.
        # We can use this to verify (and test) the outputs of the pipeline.
        self.test_mode = test_mode
        self.test_output = {}

        for operator in dataflow.operators:
            operator.meta_wrapper = None  # We set this meta wrapper to None, we don't need it in the runtime.
            self.init_operators.append(BeamInitOperator(operator))
            self.operators.append(BeamOperator(operator, self.serializer))

    def _setup_kafka_client(self) -> KafkaConsume:
        return KafkaConsume(
            consumer_config={
                "bootstrap_servers": "localhost:9092",
                "auto_offset_reset": "latest",
                "group_id": str(uuid.uuid4()),
                "topic": ["client_request", "internal"],
            },
            value_decoder=bytes,
        )

    def _setup_kafka_producer(self, topic: str) -> kafkaio.KafkaProduce:
        return kafkaio.KafkaProduce(
            servers="localhost:9092",
            topic=topic,
        )

    def _setup_pipeline(self):
        if self.test_mode:
            pipeline = beam.testing.test_pipeline.TestPipeline()
        else:
            pipeline = beam.Pipeline(options=PipelineOptions(streaming=True))

        # Setup KafkaIO.
        kafka_client = self._setup_kafka_client()
        kafka_producer = self._setup_kafka_producer("client_reply")
        kafka_producer_internal = self._setup_kafka_producer("internal")

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
                | f"{name}_stateful"
                >> beam.ParDo(operator).with_outputs("internal", main="main")
            )

            external_output = (
                operator_pipeline["main"] | f"{name}_kafka" >> kafka_producer
            )
            internal_output = (
                operator_pipeline["internal"]
                | f"{name}_kafka_internal" >> kafka_producer_internal
            )

            if self.test_mode:
                self.test_output[f"{name}_external"] = external_output
                self.test_output[f"{name}_internal"] = internal_output

        input_and_router[
            "ingress_router_output"
        ] | "direct_output_kafka" >> kafka_producer

        self.pipeline = pipeline

    def run(self):
        print("Running Beam pipeline!")
        if not self.pipeline:
            self._setup_pipeline()

        if not self.test_mode:
            self.pipeline.run()
        else:
            self.pipeline.run().wait_until_finish()
