import pytest
from tests.common.common_classes import User, stateflow
from src.client.kafka_client import (
    StateflowKafkaClient,
    Producer,
    Consumer,
    Event,
    EventType,
    FunctionAddress,
    FunctionType,
)
from src.client.class_ref import ClassRef
from unittest import mock


class TestStateflowKafkaClient:
    def setup(self):
        flow = stateflow.init()
        self.client: StateflowKafkaClient = StateflowKafkaClient.__new__(
            StateflowKafkaClient
        )

        self.producer_mock = mock.MagicMock(Producer)
        self.consumer_mock = mock.MagicMock(Consumer)

        self.client._set_producer = lambda _: self.producer_mock
        self.client._set_consumer = lambda _: self.consumer_mock

        self.consumer_mock.poll = lambda _: None

        self.client.__init__(flow, "")

    def test_simple_send(self):
        self.client.send(
            Event(
                "123",
                FunctionAddress(FunctionType("global", "User", True), "test-user"),
                EventType.Request.InvokeStateful,
                {},
            ),
            ClassRef,
        )

        self.client.running = False

        self.producer_mock.produce.assert_called_once()
