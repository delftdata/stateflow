from apache_beam import DoFn
from apache_beam.coders import BytesCoder
from apache_beam.transforms.userstate import ReadModifyWriteStateSpec
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from beam_nuggets.io import kafkaio

from src.dataflow import StatefulOperator
from typing import List, Tuple, Any, Union
from src.serialization.json_serde import JsonSerializer, SerDe
from runtime.runtime import Runtime
from src.dataflow import Dataflow, Ingress
from src.dataflow import State, Event, EventType, Operator
from apache_beam import pvalue
from apache_beam.runners.interactive.display import pipeline_graph_renderer


class IngressBeamRouter(DoFn):
    def __init__(self, operators: List[Operator], serializer: SerDe):
        self.operators: List[Operator] = operators
        self.serializer = serializer

        self.outputs = set()

        for operator in self.operators:
            if isinstance(operator, StatefulOperator):
                name: str = operator.function_type.get_full_name()

                self.outputs.add(f"{name}-{EventType.Request.InitClass}")
                self.outputs.add(f"{name}-{EventType.Request.InvokeStateful}")

    def process(
        self, element: Tuple[bytes, bytes]
    ) -> List[Union[Tuple[str, Event], Event]]:
        event: Event = self.serializer.deserialize_event(element[1])
        event_type: str = event.event_type
        route_name: str = (
            f"{event.fun_address.function_type.get_full_name()}-{event_type}"
        )

        if not isinstance(event_type, EventType.Request):
            yield (
                event.event_id,
                Event(
                    event.event_id,
                    event.fun_address,
                    EventType.Reply.FailedInvocation,
                    {
                        "error_message": "This IngressRouter only supports event requests."
                    },
                ),
            )
        elif not route_name in self.outputs:
            yield (
                event.event_id,
                Event(
                    event.event_id,
                    event.fun_address,
                    EventType.Reply.FailedInvocation,
                    {"error_message": "This event could not be routed."},
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

    def process(self, element: Tuple[str, Event]) -> Tuple[str, Any]:
        return_event = self.operator.handle_create(element[1])
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

            # Read from Kafka and route
            input_and_router = (
                pipeline
                | "kafka-input" >> kafka_client
                | beam.ParDo(self.ingress_router).with_outputs(
                    *list(self.ingress_router.outputs), main="ingress_router_output"
                )
            )

            direct_output = input_and_router["ingress_router_output"] | kafka_producer

            for operator, init_operator in zip(self.operators, self.init_operators):
                name = operator.operator.function_type.get_full_name()
                beam_operator = name >> beam.ParDo(operator)

                ingress_to_init_to_op = (
                    input_and_router[
                        f"{init_operator.operator.function_type.get_full_name()}-{EventType.Request.InitClass}"
                    ]
                    | f"init-{name}" >> beam.ParDo(init_operator)
                    | f"init-to-{name}" >> beam_operator
                )
                ingress_to_operator = (
                    input_and_router[
                        f"{operator.operator.function_type.get_full_name()}-{EventType.Request.InvokeStateful}"
                    ]
                    | beam_operator
                    | f"{name}-to-kafka" >> kafka_producer
                )

            # print(
            #     pipeline_graph_renderer.TextRenderer().render_pipeline_graph(pipeline)
            # )

            # # Forward to init stateful operator
            # init_stateful = (
            #     input_kafka
            #     | beam.ParDo(self.ingress_router)
            #     | "init_class" >> beam.ParDo(self.init_operators[0])
            #     | "stateful_operator" >> beam.ParDo(self.operators[0])
            #     | kafka_producer
            # )
