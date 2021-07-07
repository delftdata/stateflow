import json

from stateflow.client.fastapi.fastapi import (
    FastAPIClient,
    Dataflow,
    PickleSerializer,
    SerDe,
    Event,
    T,
    StateflowFuture,
    StateflowFailure,
)
import base64
import time
import boto3


class AWSLambdaFastAPIClient(FastAPIClient):
    def __init__(
        self,
        flow: Dataflow,
        function_name: str,
        serializer: SerDe = PickleSerializer(),
        timeout: int = 5,
        root: str = "stateflow",
    ):
        super().__init__(flow, serializer, timeout, root)
        self.client = boto3.client("lambda")
        self.function_name = function_name

    def setup_init(self):
        super().setup_init()

    async def send(self, event: Event, return_type: T = None):
        event_serialized: bytes = self.serializer.serialize_event(event)

        event_encoded = base64.b64encode(event_serialized)

        result = self.client.invoke(
            FunctionName=self.function_name,
            Payload=event_encoded,
        )

        result = result["Payload"].read()
        result_json = json.loads(result)["body"]
        result_event = base64.b64decode(json.loads(result_json)["event"])

        future = StateflowFuture(
            event.event_id, time.time(), event.fun_address, return_type
        )

        future.complete(self.serializer.deserialize_event(result_event))

        try:
            result = future.get()
        except StateflowFailure as exc:
            return exc

        return result

    async def send_and_wait_with_future(
        self,
        event: Event,
        future: StateflowFuture,
        timeout_msg: str = "Event timed out.",
    ):
        event_serialized: bytes = self.serializer.serialize_event(event)
        event_encoded = base64.b64encode(event_serialized).decode()

        result = self.client.invoke(
            FunctionName=self.function_name,
            Payload=json.dumps({"event": event_encoded}),
        )
        result = result["Payload"].read()
        result_json = json.loads(result)["body"]
        result_event = json.loads(result_json)["event"]
        future.complete(
            self.serializer.deserialize_event(base64.b64decode(result_event))
        )
