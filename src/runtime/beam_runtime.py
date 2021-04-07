from apache_beam import DoFn
from apache_beam.coders import StrUtf8Coder
from apache_beam.transforms.userstate import ReadModifyWriteStateSpec
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from beam_nuggets.io import kafkaio

from src.dataflow import StatefulOperator
from typing import List, Tuple, Any
import apache_beam.io.kafka as kafka

from runtime.runtime import Runtime
from src.dataflow import Dataflow
from src.dataflow import State, Event


class BeamRouter(DoFn):
    def process(self, element: Tuple[bytes, bytes]) -> List[Event]:
        event: Event = Event.deserialize(element[1])

        yield event


class BeamInitOperator(DoFn):
    def __init__(self, operator: StatefulOperator):
        self.operator = operator

    def process(self, element: Event) -> Tuple[str, Any]:
        return_event = self.operator.handle_create(element)
        yield (return_event.fun_address.key, return_event)


class BeamOperator(DoFn):

    STATE_SPEC = ReadModifyWriteStateSpec("state", StrUtf8Coder())

    def __init__(self, operator: StatefulOperator):
        self.operator = operator

    def process(
        self, element: Tuple[str, Any], operator_state=DoFn.StateParam(STATE_SPEC)
    ) -> Tuple[str, Event]:
        # print(f"Now getting event {element[1]} for user {element[0]}.")
        if operator_state.read() is not None:
            state_decoded = State.deserialize(operator_state.read())
        else:
            state_decoded = None

        # Execute event.
        return_event, updated_state = self.operator.handle(element[1], state_decoded)

        # Update state.
        if updated_state is not None:
            state_encoded = State.serialize(updated_state)
            operator_state.write(state_encoded)

        yield (return_event.event_id, Event.serialize(return_event))


class BeamRuntime(Runtime):
    def __init__(self):
        self.init_operators: List[BeamInitOperator] = []
        self.operators: List[BeamOperator] = []
        self.router = BeamRouter()

    def transform(self, dataflow: Dataflow):
        for operator in dataflow.operators:
            operator.meta_wrapper = None  # We set this meta wrapper to None, we don't need it in the runtime.
            self.init_operators.append(BeamInitOperator(operator))
            self.operators.append(BeamOperator(operator))

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
                | beam.ParDo(self.router)
                | beam.ParDo(self.init_operators[0])
                | beam.ParDo(self.operators[0])
                | kafka_producer
            )
