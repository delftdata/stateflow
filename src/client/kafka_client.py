from src.client.stateflow_client import StateflowClient, Dataflow
from src.dataflow.event import Event
from typing import Optional, Any


class StateflowKafkaClient(StateflowClient):
    def __init__(self, flow: Dataflow):
        super().__init__(flow)

    def send(self, event: Event):
        pass

    def find(self) -> Optional[Any]:
        pass
