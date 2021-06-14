import base64

from tests.common.common_classes import User, Item, stateflow
from src.runtime.aws.AWSLambdaRuntime import AWSLambdaRuntime
from src.dataflow.event import Event, EventType
from src.dataflow.event_flow import InternalClassRef
from src.serialization.pickle_serializer import PickleSerializer
from src.dataflow.args import Arguments
from src.dataflow.address import FunctionType, FunctionAddress
import uuid
import json


class TestAWSRuntime:
    def setup_handle(self):
        return AWSLambdaRuntime.get_handler(stateflow.init())

    def test_simple_event(self):
        event_id: str = str(uuid.uuid4())
        event: Event = Event(
            event_id,
            FunctionAddress(FunctionType("global", "User", True), None),
            EventType.Request.InitClass,
            {"args": Arguments({"username": "wouter"})},
        )

        serialized_event = PickleSerializer().serialize_event(event)
        json_event = {
            "Records": [{"kinesis": {"data": base64.b64encode(serialized_event)}}]
        }
        handler = self.setup_handle()

        # print(handler(json_event, None))

        event: Event = Event(
            event_id,
            FunctionAddress(FunctionType("global", "User", True), "wouter"),
            EventType.Request.InvokeStateful,
            {
                "args": Arguments(
                    {
                        "items": [
                            InternalClassRef(
                                FunctionAddress(
                                    FunctionType("globals", "Item", True), "coke"
                                )
                            ),
                            InternalClassRef(
                                FunctionAddress(
                                    FunctionType("globals", "Item", True), "pepsi"
                                )
                            ),
                        ]
                    }
                ),
                "method_name": "state_requests",
            },
        )

        serialized_event = PickleSerializer().serialize_event(event)
        json_event = {
            "Records": [{"kinesis": {"data": base64.b64encode(serialized_event)}}]
        }

        # print(handler(json_event, None))
        assert True
