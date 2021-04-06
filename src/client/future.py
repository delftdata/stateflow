from typing import Generic, TypeVar
from src.dataflow.event import FunctionAddress

T = TypeVar("T")


class StateflowFuture(Generic[T]):
    def __init__(
        self, id: str, timestamp: float, function_addr: FunctionAddress, return_type: T
    ):
        self.id: str = id
        self.timestamp: float = timestamp
        self.function_addr = function_addr
        self.return_type = return_type

    def get(self) -> T:
        pass
