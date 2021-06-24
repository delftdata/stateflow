from typing import Generic, TypeVar, Optional
from src.dataflow.event import FunctionAddress, Event
import time
from src.dataflow.event import EventType
from asyncio import Future
from collections.abc import Iterable

# Type variable used to represent the return value of a StateflowFuture.
T = TypeVar("T")


class StateflowFailure(Exception):
    """Wrapper for an exception upon completion of a StateflowFuture."""

    def __init__(self, error_msg: str):
        """Initializes a StateflowFailure.

        :param error_msg: the error message.
        """
        self.error_msg = error_msg

    def __repr__(self):
        """Representation of this StateflowFailure."""
        return f"StateflowFailure: {self.error_msg}"

    def __str__(self):
        """String representation of this StateflowFailure."""
        return f"StateflowFailure: {self.error_msg}"


class StateflowFuture(Generic[T]):
    def __init__(
        self, id: str, timestamp: float, function_addr: FunctionAddress, return_type: T
    ):
        """Initializes a Stateflow future which needs to be completed.

        :param id: the id of the request. The reply will have the same id.
        :param timestamp: the timestamp for this future. Could be used to compute a timeout.
        :param function_addr: the function address of this future.
        :param return_type: the type of the return value.
        """
        self.id: str = id
        self.timestamp: float = timestamp
        self.function_addr = function_addr
        self.return_type = return_type

        # To be completed later on.
        self.is_completed: bool = False
        self.result: Optional[T] = None

    def complete(self, event: Event):
        """Completes the future given a 'reply' event.

        :param event: the reply event from the runtime.
        """
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
        elif event.event_type == EventType.Reply.Pong:
            self.result = None
        elif event.event_type == EventType.Reply.KeyNotFound:
            self.result = StateflowFailure(event.payload["error_message"])
        else:
            raise AttributeError(
                f"Can't complete unknown even type: {event.event_type}"
            )

    def get(self, timeout=-1) -> T:
        """Gets the return value of this future.
        If not completed, it will wait until it is.

        NOTE: This might be blocking forever, if the future is never completed.

        :return: the return value.
        """
        timeout_time = time.time() + timeout
        while not self.is_completed:
            if timeout != -1 and time.time() >= timeout_time:
                raise AttributeError(
                    f"Timeout for the future {self} after {timeout} seconds."
                )
            time.sleep(0.01)

        if isinstance(self.result, list):
            if (
                len(self.result) == 1
            ):  # If there is a list with only 1 element, we return that.
                return self.result[0]
            else:
                return tuple(
                    self.result
                )  # We return lists as tuples, so it can be unpacked.

        if isinstance(
            self.result, StateflowFailure
        ):  # If it is an error, we throw a failure.
            raise StateflowFailure(self.result.error_msg)

        return self.result
