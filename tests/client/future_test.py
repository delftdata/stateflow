import pytest
from tests.common.common_classes import User, stateflow
from src.client.future import StateflowFuture, StateflowFailure
from src.dataflow.event import FunctionAddress, FunctionType, EventType, Event
from src.client.class_ref import ClassRef
from typing import List


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


def test_future_complete_failed_invocation_event():
    flow_future = StateflowFuture(
        "123", 123, FunctionAddress(FunctionType("", "", True), "key"), bool
    )
    event = Event(
        "id",
        FunctionAddress(FunctionType("", "", True), "key"),
        EventType.Reply.FailedInvocation,
        {"error_message": "this is an error!"},
    )

    with pytest.raises(StateflowFailure) as excep:
        flow_future.complete(event)
        flow_future.get()

        excep.error_msg = "this is an error!"


def test_future_complete_found_class_event():
    stateflow.init()
    flow_future = StateflowFuture(
        "123",
        123,
        FunctionAddress(FunctionType("", "", True), "test-user"),
        stateflow.meta_classes[1],
    )
    event = Event(
        "id",
        FunctionAddress(FunctionType("", "", True), "test-user"),
        EventType.Reply.FoundClass,
        {},
    )

    flow_future.complete(event)
    res = flow_future.get()

    assert isinstance(res, ClassRef)
    assert res._fun_addr.key == "test-user"


def test_future_complete_found_class_event():
    stateflow.init()
    flow_future = StateflowFuture(
        "123",
        123,
        FunctionAddress(FunctionType("", "", True), "test-user"),
        stateflow.meta_classes[1],
    )
    event = Event(
        "id",
        FunctionAddress(FunctionType("", "", True), "test-user"),
        EventType.Reply.SuccessfulCreateClass,
        {},
    )

    flow_future.complete(event)
    res = flow_future.get()

    assert isinstance(res, ClassRef)
    assert res._fun_addr.key == "test-user"


def test_future_complete_found_invocation_event():
    flow_future = StateflowFuture(
        "123",
        123,
        FunctionAddress(FunctionType("", "", True), "test-user"),
        int,
    )
    event = Event(
        "id",
        FunctionAddress(FunctionType("", "", True), "test-user"),
        EventType.Reply.SuccessfulInvocation,
        {"return_results": 1},
    )

    flow_future.complete(event)
    res = flow_future.get()

    assert isinstance(res, int)
    assert res == 1


def test_future_complete_found_invocation_event_list():
    flow_future = StateflowFuture(
        "123",
        123,
        FunctionAddress(FunctionType("", "", True), "test-user"),
        int,
    )
    event = Event(
        "id",
        FunctionAddress(FunctionType("", "", True), "test-user"),
        EventType.Reply.SuccessfulInvocation,
        {"return_results": [1]},
    )

    flow_future.complete(event)
    res = flow_future.get()

    assert isinstance(res, int)
    assert res == 1


def test_future_complete_found_invocation_event_list_multiple():
    flow_future = StateflowFuture(
        "123",
        123,
        FunctionAddress(FunctionType("", "", True), "test-user"),
        List[int],
    )
    event = Event(
        "id",
        FunctionAddress(FunctionType("", "", True), "test-user"),
        EventType.Reply.SuccessfulInvocation,
        {"return_results": [1, 3, 4]},
    )

    flow_future.complete(event)
    res = flow_future.get()

    assert res == (1, 3, 4)


def test_future_complete_state_request():
    flow_future = StateflowFuture(
        "123",
        123,
        FunctionAddress(FunctionType("", "", True), "test-user"),
        List[int],
    )
    event = Event(
        "id",
        FunctionAddress(FunctionType("", "", True), "test-user"),
        EventType.Reply.SuccessfulStateRequest,
        {"state": [1, 3, 4]},
    )

    flow_future.complete(event)
    res = flow_future.get()

    assert res == (1, 3, 4)
