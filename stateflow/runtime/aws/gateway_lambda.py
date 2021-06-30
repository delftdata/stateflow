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


class AWSGatewayLambdaRuntime(AWSLambdaRuntime):
    def __init__(
        self,
        flow: Dataflow,
        table_name="stateflow",
        serializer: SerDe = PickleSerializer(),
        config: Config = Config(region_name="eu-west-1"),
    ):
        super().__init__(flow, table_name, serializer, config)

    def handle(self, event, context):
        event_encoded = event["event"]
        event_serialized = base64.b64decode(event_encoded)

        parsed_event: Event = self.ingress_router.parse(event_serialized)
        return_route: Route = self.handle_invocation(parsed_event)

        while return_route.direction != RouteDirection.CLIENT:
            return_route = self.handle_invocation(return_route.value)

        return_event_serialized = self.egress_router.serialize(return_route.value)
        return_event_encoded = base64.b64encode(return_event_serialized)

        return {"event": return_event_encoded}
