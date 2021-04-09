from typing import Generic, TypeVar, Optional
from src.dataflow.event import FunctionAddress, Event
import time
from src.dataflow.event import EventType
from collections.abc import Iterable

T = TypeVar("T")


class StateflowFailure(Exception):
    def __init__(self, error_msg: str):
        self.error_msg = error_msg

    def __repr__(self):
        return f"StateflowFailure: {self.error_msg}"

    def __str__(self):
        return f"StateflowFailure: {self.error_msg}"


class StateflowFuture(Generic[T]):
    def __init__(
        self, id: str, timestamp: float, function_addr: FunctionAddress, return_type: T
    ):
        self.id: str = id
        self.timestamp: float = timestamp
        self.function_addr = function_addr
        self.return_type = return_type

        self.is_completed: bool = False
        self.result: Optional[T] = None

    def complete(self, event: Event):
        self.is_completed = event

        if event.event_type == EventType.Reply.FailedInvocation:
            self.result = StateflowFailure(event.payload["error_message"])
        elif event.event_type == EventType.Reply.SuccessfulCreateClass:
            self.result = self.return_type(__key=event.fun_address.key)
        elif event.event_type == EventType.Reply.SuccessfulInvocation:
            self.result = event.payload["return_results"]
        elif event.event_type == EventType.Reply.SuccessfulStateRequest:
            if "state" in event.payload:
                self.result = event.payload["state"]
        elif event.event_type == EventType.Reply.FoundClass:
            self.result = self.return_type(__key=event.fun_address.key)
        else:
            raise AttributeError(
                f"Can't complete unknown even type: {event.event_type}"
            )

    def get(self) -> T:
        while not self.is_completed:
            time.sleep(0.01)

        if isinstance(self.result, list):
            if len(self.result) == 1:
                return self.result[0]
            else:
                return tuple(self.result)

        if isinstance(self.result, StateflowFailure):
            raise StateflowFailure(self.result.error_msg)

        return self.result
