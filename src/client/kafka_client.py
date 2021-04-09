from src.client.stateflow_client import StateflowClient, Dataflow, SerDe, JsonSerializer
from src.dataflow.event import Event
from src.client.future import StateflowFuture, T
from typing import Optional, Any, List
import threading

import uuid
from confluent_kafka import Producer, Consumer
import time


class StateflowKafkaClient(StateflowClient):
    def __init__(
        self, flow: Dataflow, brokers: str, serializer: SerDe = JsonSerializer()
    ):
        super().__init__(flow, serializer)
        self.brokers = brokers

        # We should a client id later.
        # self.client_id: str = uuid.uuid4()

        # Producer and consumer.
        self.producer = Producer({"bootstrap.servers": brokers})
        self.consumer = Consumer(
            {
                "bootstrap.servers": brokers,
                "group.id": "mygroup",
                "auto.offset.reset": "earliest",
            }
        )

        # Topics are hardcoded now.
        self.req_topic = "client_request"
        self.reply_topic = "client_reply"

        # The futures still to complete.
        self.futures: dict[str, StateflowFuture] = {}

        # Set the wrapper.
        [op.meta_wrapper.set_client(self) for op in flow.operators]

        # Start consumer thread.
        self.consumer_thread = threading.Thread(target=self.start_consuming)
        self.consumer_thread.start()

    def start_consuming(self):
        self.consumer.subscribe([self.reply_topic])

        while True:
            msg = self.consumer.poll(0.01)
            if msg is None:
                continue
            if msg.error():
                print("Consumer error: {}".format(msg.error()))
                continue

            key = msg.key().decode("utf-8")
            # print(f"{key} -> Received message")
            if key in self.futures.keys():
                self.futures[key].complete(
                    self.serializer.deserialize_event(msg.value())
                )
                del self.futures[key]

            # print(self.futures.keys())
            # print("Received message: {}".format(msg.value().decode("utf-8")))

    def send(self, event: Event, return_type: T = None):
        self.producer.produce(
            self.req_topic,
            value=bytes(self.serializer.serialize_event(event), "utf-8"),
            key=bytes(event.event_id, "utf-8"),
        )

        future = StateflowFuture(
            event.event_id, time.time(), event.fun_address, return_type
        )

        self.futures[event.event_id] = future

        self.producer.flush()
        # print(f"{event.event_id} -> Send message")
        return future

    def find(self) -> Optional[Any]:
        pass
