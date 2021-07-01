from stateflow.client.fastapi.fastapi import (
    FastAPIClient,
    Dataflow,
    PickleSerializer,
    SerDe,
    Event,
    T,
    StateflowFuture,
    StateflowFailure,
    FunctionAddress,
    FunctionType,
    EventType,
)
import httpx
import uuid
import base64
import time


class AWSGatewayFastAPIClient(FastAPIClient):
    def __init__(
        self,
        flow: Dataflow,
        api_gateway_url: str,
        serializer: SerDe = PickleSerializer(),
        timeout: int = 5,
        root: str = "stateflow",
    ):
        super().__init__(flow, serializer, timeout, root)
        self.api_gateway_url: str = api_gateway_url
        self.http_client = httpx.AsyncClient()

    def setup_init(self):
        super().setup_init()

    async def send(self, event: Event, return_type: T = None):
        event_serialized: bytes = self.serializer.serialize_event(event)
        event_encoded = base64.b64encode(event_serialized).decode()

        result = await self.http_client.post(
            self.api_gateway_url, json={"event": event_encoded}, timeout=self.timeout
        )
        result_json = result.json()

        result_event = base64.b64decode(result_json["event"])

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

        try:
            result = await self.http_client.post(
                self.api_gateway_url,
                json={"event": event_encoded},
                timeout=self.timeout,
            )
        except httpx.TimeoutException:
            future.complete_with_failure(timeout_msg)
            return

        result_json = result.json()
        result_event = base64.b64decode(result_json["event"])
        future.complete(self.serializer.deserialize_event(result_event))
