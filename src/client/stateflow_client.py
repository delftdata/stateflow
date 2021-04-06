from src.dataflow import Dataflow
from typing import Optional, Any
from src.client.future import StateflowFuture, T


class StateflowClient:
    def __init__(self, flow: Dataflow):
        self.flow = flow

    def send(self) -> StateflowFuture[T]:
        pass

    def find(self) -> Optional[Any]:
        pass
