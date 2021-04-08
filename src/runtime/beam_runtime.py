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
from src.dataflow import Dataflow, Ingress,Arguments
from src.dataflow import State, Event, EventType, Operator, FunctionAddress, FunctionType
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

                self.outputs.add(f"{name}-{EventType.Request.InitClass}")
                self.outputs.add(f"{name}-{EventType.Request.InvokeStateful}")

    def process(
        self, element: Tuple[bytes, bytes]
    ) -> List[Union[Tuple[str, Any], Any]]:
        event: Event = self.serializer.deserialize_event(element[1])
        event_type: str = event.event_type
        route_name: str = (
            f"{event.fun_address.function_type.get_full_name()}-{event_type}"
        )
        print(route_name)
        if not isinstance(event_type, EventType.Request):
            return [(
                event.event_id,
                Event(
                    event.event_id,
                    event.fun_address,
                    EventType.Reply.FailedInvocation,
                    {
                        "error_message": "This IngressRouter only supports event requests."
                    },
                ),
            )]
        elif not route_name in self.outputs:
            return [ (
                event.event_id,
                Event(
                    event.event_id,
                    event.fun_address,
                    EventType.Reply.FailedInvocation,
                    {"error_message": "This event could not be routed."},
                ),
            )]
        # if the key is available, then we set that as key otherwise we set the event_id.
        elif event.fun_address.key:
            return [ pvalue.TaggedOutput(route_name, (event.fun_address.key, event))]
        else:
            return [pvalue.TaggedOutput(route_name, (event.event_id, event))]


class BeamInitOperator(DoFn):
    def __init__(self, operator: StatefulOperator):
        self.operator = operator

    @beam.typehints.with_input_types(Tuple[str, Any])
    def process(self, element: Tuple[str, Any]) -> Tuple[str, Any]:
        return_event = self.operator.handle_create(element[1])
        print(f"{return_event} with key {return_event.fun_address.key}")
        yield (return_event.fun_address.key, return_event)


class BeamOperator(DoFn):

    STATE_SPEC = ReadModifyWriteStateSpec("state", BytesCoder())

    def __init__(self, operator: StatefulOperator, serializer: SerDe):
        self.operator = operator
        self.serializer = serializer

    @beam.typehints.with_input_types(Tuple[str, Any])
    def process(
        self, element: Tuple[str, Any], operator_state=DoFn.StateParam(STATE_SPEC)
    ) -> Tuple[str, Any]:
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

        opt = PipelineOptions(["--runner=FlinkRunner", "--environment_type=LOOPBACK"])

        with beam.Pipeline(options=PipelineOptions(streaming=True)) as pipeline:

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
                | "kafka-input" >> beam.Create([(bytes("123", 'utf-8'), bytes(self.serializer.serialize_event(Event("123", FunctionAddress(FunctionType("global", "Fun", True), None), EventType.Request.InitClass, {"args": Arguments({"username": "wouter"})})), 'utf-8'))])#kafka_client
                | beam.ParDo(self.ingress_router).with_outputs(
                    *list(self.ingress_router.outputs), main="ingress_router_output"
                )
            )

            print(input_and_router)

            operator_outputs = []
            for operator, init_operator in zip(self.operators, self.init_operators):
                name = operator.operator.function_type.get_full_name()

                init_class = input_and_router[
                    f"{init_operator.operator.function_type.get_full_name()}-{EventType.Request.InitClass}"
                ]

                ingress_to_init_to_op = init_class | f"init-{name}" >> beam.ParDo(
                    init_operator
                )

                invoke_stateful = input_and_router[
                    f"{operator.operator.function_type.get_full_name()}-{EventType.Request.InvokeStateful}"
                ]

                flatten_input = ((invoke_stateful,ingress_to_init_to_op) | "flatten" >> beam.Flatten())

                print(ingress_to_init_to_op)
                operator_final = flatten_input | beam.ParDo(operator)
                operator_outputs.append(operator_final)

            operator_outputs.append(input_and_router["ingress_router_output"])

            final = operator_outputs | "Flat final" >> beam.Flatten() | beam.Map(print)#kafka_producer

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

            pipeline.run()
