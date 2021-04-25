import os
import uuid

import pytest

from tests.common.common_classes import User, stateflow
from src.dataflow.event import Event, FunctionAddress, FunctionType, EventType
from src.dataflow.args import Arguments
from src.dataflow.stateful_operator import StatefulOperator


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

    def test_handle_init_class(self):
        pass
