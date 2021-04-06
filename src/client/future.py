from typing import Generic, TypeVar, Optional
from src.dataflow.event import FunctionAddress, Event
import time


T = TypeVar("T")


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
        self.result = event

    def get(self) -> T:
        while not self.is_completed:
            time.sleep(0.01)

        return self.result
