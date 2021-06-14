from src.client.stateflow_client import StateflowClient
from src.serialization.pickle_serializer import PickleSerializer, SerDe
from src.dataflow.dataflow import Dataflow
from src.dataflow.event import Event, EventType
from src.dataflow.address import FunctionType, FunctionAddress
from src.client.future import StateflowFuture, T
from typing import Dict, Optional, Any
import boto3
import time
import threading
import uuid


class AWSKinesisClient(StateflowClient):
    def __init__(
        self,
        flow: Dataflow,
        request_stream: str = "stateflow-request",
        reply_stream: str = "stateflow-reply",
        serializer: SerDe = PickleSerializer(),
    ):
        self.flow = flow
        self.request_stream = request_stream
        self.reply_stream = reply_stream
        self.serializer = serializer

        self.kinesis = boto3.client("kinesis")
        self.request_stream: str = request_stream
        self.reply_stream: str = reply_stream

        # The futures still to complete.
        self.futures: Dict[str, StateflowFuture] = {}

        # Set the wrapper.
        [op.meta_wrapper.set_client(self) for op in flow.operators]

        if not self.does_stream_exist(request_stream):
            self.create_stream(request_stream)

        if not self.does_stream_exist(reply_stream):
            self.create_stream(reply_stream)

        self.running = True
        consume_thread = threading.Thread(target=self.consume)
        consume_thread.start()

    def does_stream_exist(self, name: str) -> bool:
        try:
            print(self.kinesis.describe_stream(StreamName=name))
        except Exception:
            return False

        return True

    def create_stream(self, name: str):
        self.kinesis.create_stream(StreamName=name, ShardCount=1)

    def consume(self):
        iterator = self.kinesis.get_shard_iterator(
            StreamName=self.reply_stream, ShardId="0", ShardIteratorType="LATEST"
        )["ShardIterator"]

        while self.running:
            response = self.kinesis.get_records(ShardIterator=iterator)
            iterator = response["NextShardIterator"]
            for msg in response["Records"]:
                event_serialized = msg["Data"]
                event = self.serializer.deserialize_event(event_serialized)
                key = event.event_id

                # print(f"{key} -> Received message")
                if key in self.futures.keys():
                    if not event:
                        event = self.serializer.deserialize_event(msg.value())
                    self.futures[key].complete(event)
                    del self.futures[key]

            time.sleep(0.01)

    def find(self, clasz, key: str) -> StateflowFuture[Optional[Any]]:
        event_id = str(uuid.uuid4())
        event_type = EventType.Request.FindClass
        fun_address = FunctionAddress(FunctionType.create(clasz.descriptor), key)
        payload = {}

        return self.send(Event(event_id, fun_address, event_type, payload), clasz)

    def send(self, event: Event, return_type: T = None) -> StateflowFuture[T]:
        send_record = self.kinesis.put_record(
            StreamName=self.request_stream,
            Data=self.serializer.serialize_event(event),
            PartitionKey=event.event_id,
        )

        future = StateflowFuture(
            event.event_id, time.time(), event.fun_address, return_type
        )

        self.futures[event.event_id] = future

        return future
