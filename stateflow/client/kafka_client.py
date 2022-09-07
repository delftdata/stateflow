from stateflow.client.stateflow_client import StateflowClient, SerDe
from stateflow.serialization.pickle_serializer import PickleSerializer
from stateflow.dataflow.dataflow import Dataflow, IngressRouter
from stateflow.dataflow.event import Event, FunctionAddress, EventType
from stateflow.dataflow.address import FunctionType
from stateflow.client.future import StateflowFuture, T
from typing import Optional, Any, Dict
import threading

import pandas as pd
import uuid
from confluent_kafka import Producer, Consumer
from confluent_kafka.admin import AdminClient, NewTopic
import time


class StateflowKafkaClient(StateflowClient):
    def __init__(
        self,
        flow: Dataflow,
        brokers: str,
        serializer: SerDe = PickleSerializer(),
        statefun_mode: bool = False,
    ):
        super().__init__(flow, serializer)
        self.brokers = brokers

        # We should set a client id later.
        # self.client_id: str = uuid.uuid4()
        self.statefun_mode: bool = statefun_mode

        # Producer and consumer.
        self.producer = self._set_producer(brokers)
        self.consumer = self._set_consumer(brokers)
        self.function_results_consumer = self._set_consumer(brokers)

        # Topics are hardcoded now, should be configurable later on.
        self.req_topic = "client_request"
        self.reply_topic = "client_reply"

        self.ingress_router = IngressRouter(self.serializer)

        # The futures still to complete.
        self.futures: Dict[str, StateflowFuture] = {}

        # Set the wrapper.
        self.operators = flow.operators
        [op.meta_wrapper.set_client(self) for op in flow.operators]

        self.timestamped_request_ids = {}
        # Start consumer thread.
        self.running = True
        self.consumer_thread = threading.Thread(target=self.start_consuming)
        self.consumer_thread.start()

        self.running_result_consumer = False
        self.result_consumer_process = threading.Thread(target=self.start_consuming_function_results)

    def start_result_consumer_process(self):
        self.running_result_consumer = True
        self.result_consumer_process.start()

    def stop_result_consumer_process(self):
        self.running_result_consumer = False

    def _set_producer(self, brokers: str) -> Producer:
        return Producer({"bootstrap.servers": brokers})

    def _set_consumer(self, brokers: str) -> Consumer:
        return Consumer(
            {
                "bootstrap.servers": brokers,
                "group.id": str(uuid.uuid4()),
                "auto.offset.reset": "latest",
            }
        )

    def start_consuming_function_results(self):
        records = []
        self.function_results_consumer.subscribe([self.reply_topic])

        while self.running_result_consumer:
            msg = self.function_results_consumer.poll(0.01)
            if msg is None:
                continue

            if msg.error():
                continue
            records.append((msg.key().decode("utf-8"), msg.timestamp()[1]))
        self.function_results_consumer.close()
        pd.DataFrame.from_records(records, columns=['request_id', 'timestamp']).to_csv('output.csv', index=False)

    def stop_consumer_thread(self):
        self.running = False

    def start_consuming(self):
        self.consumer.subscribe([self.reply_topic])

        while self.running:
            msg = self.consumer.poll(0.01)
            if msg is None:
                continue
            if msg.error():
                # print("Consumer error: {}".format(msg.error()))
                continue

            if msg.key() is None:
                event = self.serializer.deserialize_event(msg.value())
                key = event.event_id
            else:
                event = None
                key = msg.key().decode("utf-8")

            # print(f"{key} -> Received message")
            if key in self.futures.keys():
                if not event:
                    event = self.serializer.deserialize_event(msg.value())
                self.futures[key].complete(event)
                del self.futures[key]
        self.consumer.close()
        print('Future consumer exited successfully')

    def send(self, event: Event, return_type: T = None):
        if not self.statefun_mode:
            self.producer.produce(
                self.req_topic,
                value=self.serializer.serialize_event(event),
                key=bytes(event.event_id, "utf-8"),
            )
        else:
            route = self.ingress_router.route(event)
            topic = route.route_name.replace("/", "_")
            key = route.key or event.event_id

            if not route.key:
                topic = topic + "_create"
            # print(f"Sending to {topic} with key {key}")

            self.producer.produce(
                topic,
                value=self.serializer.serialize_event(event),
                key=key,
            )
        if not self.running:
            self.timestamped_request_ids[event.event_id] = int(round(time.time() * 1000))  # to ms

        future = StateflowFuture(
            event.event_id, time.time(), event.fun_address, return_type
        )

        self.futures[event.event_id] = future

        self.producer.flush()
        # print(f"{event.event_id} -> Send message")
        return future

    def find(self, clasz, key: str) -> StateflowFuture[Optional[Any]]:
        event_id = str(uuid.uuid4())
        event_type = EventType.Request.FindClass
        fun_address = FunctionAddress(FunctionType.create(clasz.descriptor), key)
        payload = {}

        return self.send(Event(event_id, fun_address, event_type, payload), clasz)

    def create_all_topics(self):
        admin = AdminClient({"bootstrap.servers": self.brokers})
        topics_to_create = []

        if self.statefun_mode:
            topics_to_create.append(
                NewTopic("globals_ping", num_partitions=1, replication_factor=1)
            )

            for operator in self.operators:
                topics_to_create.append(
                    NewTopic(
                        operator.function_type.get_full_name().replace("/", "_"),
                        num_partitions=1,
                        replication_factor=1,
                    )
                )
                topics_to_create.append(
                    NewTopic(
                        f"{operator.function_type.get_full_name().replace('/', '_')}_create",
                        num_partitions=1,
                        replication_factor=1,
                    )
                )
        else:
            topics_to_create.append(
                NewTopic("internal", num_partitions=10, replication_factor=1)
            )
            topics_to_create.append(
                NewTopic("client_request", num_partitions=10, replication_factor=1)
            )

        topics_to_create.append(
            NewTopic("client_reply", num_partitions=10, replication_factor=1)
        )

        for topic, f in admin.create_topics(topics_to_create).items():
            try:
                f.result()  # The result itself is None
                print("Topic {} created".format(topic))
            except Exception as e:
                print("Failed to create topic {}: {}".format(topic, e))

    def _send_ping(self) -> StateflowFuture:
        event = Event(
            str(uuid.uuid4()),
            FunctionAddress(FunctionType("", "", False), None),
            EventType.Request.Ping,
            {},
        )

        topic = self.req_topic if not self.statefun_mode else "globals_ping"

        self.producer.produce(
            topic,
            value=self.serializer.serialize_event(event),
            key=bytes(event.event_id, "utf-8"),
        )

        future = StateflowFuture(event.event_id, time.time(), event.fun_address, None)

        self.futures[event.event_id] = future
        self.producer.flush()

        return future

    def wait_until_healthy(self, timeout=0.5) -> bool:
        pong = False

        while not pong:
            pong_future = self._send_ping()

            try:
                pong_future.get(timeout=timeout)
                print("Got a pong!")
                pong = True
            except AttributeError:  # future timeout
                print("Not a pong yet :(")
                del self.futures[pong_future.id]

        return pong

    def store_request_csv(self):
        pd.DataFrame(self.timestamped_request_ids.items(),
                     columns=['request_id', 'timestamp']).to_csv('universalis_client_requests.csv', index=False)
