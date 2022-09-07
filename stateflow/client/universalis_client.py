import threading
import uuid
import pandas as pd
from typing import Dict, Optional, Any

from confluent_kafka import Consumer
from universalis.common.operator import Operator
from universalis.common.serialization import Serializer, pickle_deserialization, msgpack_deserialization
from universalis.universalis import Universalis

from stateflow.client.future import T, StateflowFuture
from stateflow.client.stateflow_client import StateflowClient
from stateflow.dataflow.address import FunctionAddress, FunctionType
from stateflow.dataflow.dataflow import Dataflow, IngressRouter
from stateflow.dataflow.event import Event, EventType


class UniversalisClient(StateflowClient):

    def __init__(self,
                 flow: Dataflow,
                 universalis_client: Universalis,
                 kafka_url: str,
                 operators: dict[str, Operator]):

        super().__init__(flow)

        self.universalis_client = universalis_client

        # Producer and consumer.
        self.consumer = self._set_consumer(kafka_url)
        self.function_results_consumer = self._set_consumer(kafka_url)

        self.reply_topic = "universalis-egress"

        self.ingress_router = IngressRouter(self.serializer)

        # The futures still to complete.
        self.futures: Dict[str, StateflowFuture] = {}

        self.stateflow_operators = {}
        for operator in flow.operators:
            self.stateflow_operators[f"{operator.function_type.get_safe_full_name()}"] = operator
        # Set the wrapper.
        [op.meta_wrapper.set_client(self) for op in flow.operators]

        self.operators: dict[str, Operator] = operators
        self.created_topics = set()

        self.timestamped_request_ids = {}

        # Start consumer thread.
        self.running = True
        self.consumer_process = threading.Thread(target=self.start_consuming)
        self.consumer_process.start()

        self.running_result_consumer = False
        self.result_consumer_process = threading.Thread(target=self.start_consuming_function_results)

    def start_result_consumer_process(self):
        self.running_result_consumer = True
        self.result_consumer_process.start()

    def stop_result_consumer_process(self):
        self.running_result_consumer = False

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
            records.append((msgpack_deserialization(msg.key()), msg.timestamp()[1]))
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
                # print(f"CLIENT \tConsumer error: {msg.error()}")
                continue

            key = msgpack_deserialization(msg.key())
            event: Event = pickle_deserialization(msg.value())
            if isinstance(event, str):
                print(f"CLIENT \t{key} -> Received message: {event}")
            else:
                print(f"CLIENT \t{key} -> Received message: {event.payload}")

            if event.event_id in self.futures.keys():
                self.futures[event.event_id].complete(event)
                del self.futures[event.event_id]
        self.consumer.close()
        print('Future consumer exited successfully')

    def send(self, event: Event, return_type: T = None):
        route = self.ingress_router.route(event)
        topic = route.route_name.replace("/", "_")
        key = route.key or event.event_id
        if not route.key:
            topic = topic + "_create"
            function_name = "UniversalisCreateOperator"
        else:
            function_name = "UniversalisOperator"
        # print(f'CLIENT \tsending event: {event.payload} at key: {event.fun_address.key}')
        request_id, timestamp = self.universalis_client.send_kafka_event_no_wait(self.operators[topic],
                                                                                 key,
                                                                                 function_name,
                                                                                 (event, ),
                                                                                 serializer=Serializer.PICKLE)
        if not self.running:
            self.timestamped_request_ids[request_id] = timestamp
        future = StateflowFuture(event.event_id, timestamp, event.fun_address, return_type)

        self.futures[event.event_id] = future
        self.universalis_client.sync_kafka_producer.flush()
        return future

    def find(self, clasz, key: str) -> StateflowFuture[Optional[Any]]:
        event_id = str(uuid.uuid4())
        event_type = EventType.Request.FindClass
        fun_address = FunctionAddress(FunctionType.create(clasz.descriptor), key)
        payload = {}
        print('CLIENT \tSending find')
        return self.send(Event(event_id, fun_address, event_type, payload), clasz)

    def _send_ping(self) -> StateflowFuture:

        event = Event(
            str(uuid.uuid4()),
            FunctionAddress(FunctionType("", "", False), None),
            EventType.Request.Ping,
            {},
        )
        print(f'CLIENT \tSending ping with id: {event.event_id}')
        request_id, timestamp = self.universalis_client.send_kafka_event_no_wait(operator=self.operators["global_Ping"],
                                                                                 key=event.event_id,
                                                                                 function="UniversalisPingOperator",
                                                                                 params=(event, ),
                                                                                 serializer=Serializer.PICKLE)

        future = StateflowFuture(event.event_id, timestamp, event.fun_address, None)
        self.futures[event.event_id] = future
        self.universalis_client.sync_kafka_producer.flush()
        return future

    def wait_until_healthy(self, timeout=0.5) -> bool:
        pong = False

        while not pong:
            pong_future = self._send_ping()

            try:
                pong_future.get(timeout=timeout)
                print("CLIENT \tGot a pong!")
                pong = True
            except AttributeError:  # future timeout
                print("CLIENT \tNot a pong yet :(")
                del self.futures[pong_future.id]

        return pong

    def store_request_csv(self):
        pd.DataFrame(self.timestamped_request_ids.items(),
                     columns=['request_id', 'timestamp']).to_csv('universalis_client_requests.csv', index=False)
