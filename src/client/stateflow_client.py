from src.dataflow import Dataflow
from typing import Optional, Any, List
from src.client.future import StateflowFuture, T
from src.serialization.json_serde import SerDe, JsonSerializer
import time


class StateflowClient:
    def __init__(self, flow: Dataflow, serializer: SerDe = JsonSerializer):
        self.flow = flow
        self.serializer: SerDe = serializer

    def send(self) -> StateflowFuture[T]:
        pass

    def find(self) -> Optional[Any]:
        pass

    def await_futures(self, future_list: List[StateflowFuture[T]]):
        waiting_for = [fut for fut in future_list if not fut.is_completed]
        while len(waiting_for):
            waiting_for = [fut for fut in future_list if not fut.is_completed]
