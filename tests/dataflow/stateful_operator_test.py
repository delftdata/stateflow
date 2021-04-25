import os
import uuid

import pytest

from tests.common.common_classes import User, stateflow
from src.dataflow.event import Event, FunctionAddress, FunctionType, EventType
from src.dataflow.args import Arguments
from src.dataflow.state import State
from src.dataflow.stateful_operator import StatefulOperator
from src.serialization.json_serde import JsonSerializer


class TestStatefulOperator:
    def setup(self):
        print("I'm here")
        flow = stateflow.init()
        self.item_operator = flow.operators[0]
        self.user_operator = flow.operators[1]

    def test_init_class_negative(self):
        # TODO create this
        pass

    def test_init_class_positive(self):
        operator: StatefulOperator = self.user_operator

        event_id = str(uuid.uuid4())
        event = Event(
            event_id,
            FunctionAddress(FunctionType("global", "User", True), None),
            EventType.Request.InitClass,
            {"args": Arguments({"username": "wouter"})},
        )

        return_event = operator.handle_create(event)

        assert return_event.event_id == event_id
        assert return_event.fun_address.key == "wouter"
        assert return_event.payload == {
            "init_class_state": {"username": "wouter", "balance": 0, "items": []}
        }

    def test_handle_init_class_positive(self):
        operator: StatefulOperator = self.user_operator

        event_id = str(uuid.uuid4())
        event = Event(
            event_id,
            FunctionAddress(FunctionType("global", "User", True), None),
            EventType.Request.InitClass,
            {"args": Arguments({"username": "wouter"})},
        )

        intermediate_event = operator.handle_create(event)
        return_event, state = operator.handle(intermediate_event, None)

        assert state is not None
        assert return_event.event_type == EventType.Reply.SuccessfulCreateClass
        assert return_event.payload["key"] == "wouter"

    def test_handle_init_class_negative(self):
        operator: StatefulOperator = self.user_operator

        event_id = str(uuid.uuid4())
        event = Event(
            event_id,
            FunctionAddress(FunctionType("global", "User", True), None),
            EventType.Request.InitClass,
            {"args": Arguments({"username": "wouter"})},
        )

        intermediate_event = operator.handle_create(event)
        return_event, state = operator.handle(intermediate_event, "non_empty_state")

        assert state == "non_empty_state"
        assert return_event.event_type == EventType.Reply.FailedInvocation
        assert return_event.payload["error_message"]

    def test_invoke_stateful_positive(self):
        operator: StatefulOperator = self.user_operator

        event_id = str(uuid.uuid4())
        event = Event(
            event_id,
            FunctionAddress(FunctionType("global", "User", True), "wouter"),
            EventType.Request.InvokeStateful,
            {"args": Arguments({"x": 5}), "method_name": "update_balance"},
        )

        state = State({"username": "wouter", "balance": 10, "items": []})
        return_event, updated_state_bytes = operator.handle(
            event, TestStatefulOperator.state_to_bytes(state)
        )
        updated_state = TestStatefulOperator.bytes_to_state(updated_state_bytes)

        assert return_event.event_type == EventType.Reply.SuccessfulInvocation
        assert return_event.payload["return_results"] is None
        assert updated_state["balance"] == 15

    def test_invoke_stateful_negative(self):
        operator: StatefulOperator = self.user_operator

        event_id = str(uuid.uuid4())
        event = Event(
            event_id,
            FunctionAddress(FunctionType("global", "User", True), "wouter"),
            EventType.Request.InvokeStateful,
            {"args": Arguments({"x": "100"}), "method_name": "update_balance"},
        )

        state = State({"username": "wouter", "balance": 10, "items": []})
        return_event, updated_state_bytes = operator.handle(
            event, TestStatefulOperator.state_to_bytes(state)
        )
        updated_state = TestStatefulOperator.bytes_to_state(updated_state_bytes)

        assert return_event.event_type == EventType.Reply.FailedInvocation
        assert updated_state["balance"] == 10

    @staticmethod
    def bytes_to_state(state: bytes) -> State:
        return State(JsonSerializer().deserialize_dict(state))

    @staticmethod
    def state_to_bytes(state: State) -> bytes:
        return bytes(JsonSerializer().serialize_dict(state.get()), "utf-8")
