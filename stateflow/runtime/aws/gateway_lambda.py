import json

from stateflow.runtime.aws.abstract_lambda import (
    AWSLambdaRuntime,
    Dataflow,
    SerDe,
    Config,
    PickleSerializer,
    Event,
    RouteDirection,
    Route,
)
import base64
import time


class AWSGatewayLambdaRuntime(AWSLambdaRuntime):
    def __init__(
        self,
        flow: Dataflow,
        table_name="stateflow",
        gateway: bool = True,
        serializer: SerDe = PickleSerializer(),
        config: Config = Config(region_name="eu-west-2"),
    ):
        super().__init__(flow, table_name, serializer, config)
        self.gateway = gateway

        self.current_experiment_data = {}

    def handle(self, event, context):
        if self.gateway:
            event_body = json.loads(event["body"])
            event_encoded = event_body["event"]
            event_serialized = base64.b64decode(event_encoded)
        else:
            event_body = event["event"]
            event_serialized = base64.b64decode(event_body)

        self.current_experiment_data = {
            "STATE_SERIALIZATION_DURATION": 0,
            "EVENT_SERIALIZATION_DURATION": 0,
            "ROUTING_DURATION": 0,
            "ACTOR_CONSTRUCTION": 0,
            "EXECUTION_GRAPH_TRAVERSAL": 0,
            "KEY_LOCKING": 0,
            "READ_STATE": 0,
            "WRITE_STATE": 0,
        }

        start = time.perf_counter()
        parsed_event: Event = self.ingress_router.parse(event_serialized)
        end = time.perf_counter()
        time_ms = (end - start) * 1000
        print(f"Deser took {time_ms}")

        self.current_experiment_data["EVENT_SERIALIZATION_DURATION"] += time_ms

        return_route: Route = self.handle_invocation(parsed_event)

        while return_route.direction != RouteDirection.CLIENT:
            return_route = self.handle_invocation(return_route.value)

        start = time.perf_counter()
        return_event_serialized = self.egress_router.serialize(return_route.value)
        end = time.perf_counter()
        time_ms = (end - start) * 1000
        self.current_experiment_data["EVENT_SERIALIZATION_DURATION"] += time_ms
        print(f"Ser took {time_ms}")

        return_route.value.payload.update(self.current_experiment_data)
        return_event_serialized = self.egress_router.serialize(return_route.value)

        return_event_encoded = base64.b64encode(return_event_serialized)

        self.current_experiment_data = {}

        return {
            "statusCode": 200,
            "body": json.dumps({"event": return_event_encoded.decode()}),
        }
