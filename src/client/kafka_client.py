from src.client.stateflow_client import StateflowClient, Dataflow
from src.dataflow.event import Event


class StateflowKafkaClient(StateflowClient):
    def __init__(self, flow: Dataflow):
        super().__init__(flow)

    def send(self, event: Event):
        pass
