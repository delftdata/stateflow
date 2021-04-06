from src.client.stateflow_client import StateflowClient, Dataflow
from src.dataflow.event import Event
from src.client.future import StateflowFuture, T
from typing import Optional, Any, List

import uuid
from confluent_kafka import Producer
import time


class StateflowKafkaClient(StateflowClient):
    def __init__(self, flow: Dataflow, brokers: str):
        super().__init__(flow)
        self.brokers = brokers
        self.client_id: str = uuid.uuid4()
        self.producer = Producer({"bootstrap.servers": brokers})

        # Topics are hardcoded now.
        self.req_topic = "client_request"
        self.reply_topic = "client_result"

        self.futures: List[StateflowFuture] = []

        # Set the wrapper.
        [op.meta_wrapper.set_client(self) for op in flow.operators]

    def send(self, event: Event, return_type: T):

        self.producer.produce(
            self.req_topic, value=Event.serialize(event), key=self.client_id
        )

        return StateflowFuture(
            event.event_id, time.time(), event.fun_address, return_type
        )

    def find(self) -> Optional[Any]:
        pass
