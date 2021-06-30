import base64

import boto3

from stateflow.client.stateflow_client import StateflowClient
from stateflow.dataflow.dataflow import Dataflow
from stateflow.serialization.pickle_serializer import SerDe, PickleSerializer
from stateflow.dataflow.event import Event
from stateflow.client.future import StateflowFuture, T
import time
import requests
import json


class AWSGatewayClient(StateflowClient):
    def __init__(
        self,
        flow: Dataflow,
        api_gateway_url: str,
        serde: SerDe = PickleSerializer(),
    ):
        super().__init__(flow, serde)

        # Set the wrapper.
        [op.meta_wrapper.set_client(self) for op in flow.operators]

        self.api_gateway_url = api_gateway_url

    def send(self, event: Event, return_type: T = None) -> StateflowFuture[T]:
        event_serialized: bytes = self.serializer.serialize_event(event)
        event_encoded = base64.b64encode(event_serialized).decode()

        result = requests.post(self.api_gateway_url, json={"event": event_encoded})
        result_json = result.json()
        result_event = base64.b64decode(result_json["event"])

        fut = StateflowFuture(
            event.event_id, time.time(), event.fun_address, return_type
        )

        fut.complete(self.serializer.deserialize_event(result_event))

        return fut
