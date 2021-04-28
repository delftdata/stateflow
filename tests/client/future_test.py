import pytest
from src.client.future import StateflowFuture, StateflowFailure
from src.dataflow.event import FunctionAddress, FunctionType, EventType, Event


def test_simple_future_complete():
    flow_future = StateflowFuture(
        "123", 123, FunctionAddress(FunctionType("", "", True), "key"), bool
    )

    flow_future.is_completed = True
    flow_future.result = True

    assert flow_future.get() is True
    assert flow_future.id == "123"
    assert flow_future.timestamp == 123


def test_simple_future_complete_failure():
    flow_future = StateflowFuture(
        "123", 123, FunctionAddress(FunctionType("", "", True), "key"), bool
    )

    flow_future.is_completed = True
    flow_future.result = StateflowFailure("error!")

    with pytest.raises(StateflowFailure):
        flow_future.get()
        assert flow_future.id == "123"
        assert flow_future.timestamp == 123


def test_future_complete_unknown_event():
    flow_future = StateflowFuture(
        "123", 123, FunctionAddress(FunctionType("", "", True), "key"), bool
    )
    event = Event(
        "id", FunctionAddress(FunctionType("", "", True), "key"), "UNKNOWN", {}
    )
    with pytest.raises(AttributeError):
        flow_future.complete(event)
