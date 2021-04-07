from apache_beam import DoFn
from apache_beam.coders import BytesCoder
from apache_beam.transforms.userstate import ReadModifyWriteStateSpec
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from beam_nuggets.io import kafkaio

from src.dataflow import StatefulOperator
from typing import List, Tuple, Any
from src.serialization.json_serde import JsonSerializer, SerDe
from runtime.runtime import Runtime
from src.dataflow import Dataflow
from src.dataflow import State, Event


class BeamRouter(DoFn):
    def __init__(self, serializer: SerDe):
        self.serializer = serializer

    def process(self, element: Tuple[bytes, bytes]) -> List[Event]:
        event: Event = self.serializer.deserialize_event(element[1])

        yield event


class BeamInitOperator(DoFn):
    def __init__(self, operator: StatefulOperator):
        self.operator = operator

    def process(self, element: Event) -> Tuple[str, Any]:
        return_event = self.operator.handle_create(element)
        yield (return_event.fun_address.key, return_event)


class BeamOperator(DoFn):

    STATE_SPEC = ReadModifyWriteStateSpec("state", BytesCoder())

    def __init__(self, operator: StatefulOperator, serializer: SerDe):
        self.operator = operator
        self.serializer = serializer

    def process(
        self, element: Tuple[str, Event], operator_state=DoFn.StateParam(STATE_SPEC)
    ) -> Tuple[str, Event]:
        print(f"Executing event for {element[0]}")
        print(f"{operator_state.read()}")
        # Execute event.
        return_event, updated_state = self.operator.handle(
            element[1], operator_state.read()
        )

        # Update state.
        if updated_state is not None:
            operator_state.write(updated_state)

        yield (return_event.event_id, self.serializer.serialize_event(return_event))


class BeamRuntime(Runtime):
    def __init__(self, serializer: SerDe = JsonSerializer()):
        self.init_operators: List[BeamInitOperator] = []
        self.operators: List[BeamOperator] = []

        self.serializer = serializer
        self.ingress_router = BeamRouter(serializer)
        self.egress_router = BeamRouter(serializer)

    def transform(self, dataflow: Dataflow):
        for operator in dataflow.operators:
            operator.meta_wrapper = None  # We set this meta wrapper to None, we don't need it in the runtime.
            self.init_operators.append(BeamInitOperator(operator))
            self.operators.append(BeamOperator(operator, self.serializer))

    def run(self):
        print("Running Beam pipeline!")

        # opt = PipelineOptions(["--runner=FlinkRunner", "--environment_type=LOOPBACK"])

        with beam.Pipeline(
            options=PipelineOptions(
                streaming=True,
            )
        ) as pipeline:

            kafka_client = kafkaio.KafkaConsume(
                consumer_config={
                    "bootstrap_servers": "localhost:9092",
                    "auto_offset_reset": "earliest",
                    "group_id": "nowwww",
                    "topic": "client_request",
                }
            )

            kafka_producer = kafkaio.KafkaProduce(
                servers="localhost:9092",
                topic="client_reply",
            )

            # Read from Kafka
            input_kafka = pipeline | kafka_client

            # Forward to init stateful operator
            init_stateful = (
                input_kafka
                | beam.ParDo(self.ingress_router)
                | "init_class" >> beam.ParDo(self.init_operators[0])
                | "stateful_operator" >> beam.ParDo(self.operators[0])
                | kafka_producer
            )
