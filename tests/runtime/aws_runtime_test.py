import base64

from tests.common.common_classes import User, Item, stateflow
from src.runtime.aws.AWSLambdaRuntime import AWSLambdaRuntime
from src.dataflow.event import Event, EventType
from src.dataflow.event_flow import InternalClassRef
from src.dataflow.state import State
from src.serialization.pickle_serializer import PickleSerializer
from src.serialization.json_serde import JsonSerializer
from src.dataflow.args import Arguments
from src.dataflow.address import FunctionType, FunctionAddress
from python_dynamodb_lock.python_dynamodb_lock import *
import uuid
import json
from unittest import mock


class TestAWSRuntime:
    def setup_handle(self):
        return AWSLambdaRuntime.get_handler(stateflow.init())

    def test_simple_event(self):
        kinesis_mock = mock.MagicMock()
        lock_mock = mock.MagicMock(DynamoDBLockClient)

        AWSLambdaRuntime._setup_dynamodb = lambda x, y: None
        AWSLambdaRuntime._setup_kinesis = lambda x, y: kinesis_mock
        AWSLambdaRuntime._setup_lock_client = lambda x, y: lock_mock

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

        inst, handler = self.setup_handle()

        inst.get_state = lambda x: None
        inst.save_state = lambda x, y: None

        handler(json_event, None)

        lock_mock.acquire_lock.assert_called_once()
        kinesis_mock.put_record.assert_called_once()

        lock_mock.reset_mock()
        kinesis_mock.reset_mock()

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

        inst.get_state = lambda x: JsonSerializer().serialize_dict(
            State({"username": "wouter", "x": 5}).get()
        )

        handler(json_event, None)

        lock_mock.acquire_lock.assert_called_once()
        kinesis_mock.put_record.assert_called_once()
