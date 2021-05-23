from src.dataflow.dataflow import Dataflow
from src.serialization.json_serde import JsonSerializer, SerDe
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import asyncio
from asyncio import Future
import uuid
from src.dataflow.event import Event, EventType
from src.client.future import T, StateflowFailure
from typing import Dict


class StateflowKafkaClient:
    @classmethod
    async def create(
        cls, flow: Dataflow, brokers: str, serializer: SerDe = JsonSerializer()
    ):
        self = StateflowKafkaClient()
        self.flow = flow
        self.brokers = brokers
        self.serializer = serializer

        self.req_topic = "client_request"
        self.reply_topic = "client_reply"

        self.loop = asyncio.get_event_loop()
        self.futures: Dict[str, (T, Future)] = {}

        # Setup producer
        self.producer = AIOKafkaProducer(bootstrap_servers=brokers)
        await self.producer.start()

        # Setup consumer
        self.consumer = AIOKafkaConsumer(
            self.reply_topic,
            bootstrap_servers=brokers,
            group_id=str(uuid.uuid4()),
            auto_offset_reset="latest",
        )
        await self.consumer.start()

        return self

    def parse_result(self, event: Event, return_type: T):
        if event.event_type == EventType.Reply.FailedInvocation:
            return StateflowFailure(event.payload["error_message"])
        elif event.event_type == EventType.Reply.SuccessfulCreateClass:
            return return_type(__key=event.fun_address.key)
        elif event.event_type == EventType.Reply.SuccessfulInvocation:
            return event.payload["return_results"]
        elif event.event_type == EventType.Reply.SuccessfulStateRequest:
            if "state" in event.payload:
                return event.payload["state"]
        elif event.event_type == EventType.Reply.FoundClass:
            return return_type(__key=event.fun_address.key)
        elif event.event_type == EventType.Reply.Pong:
            return None
        else:
            raise AttributeError(
                f"Can't complete unknown even type: {event.event_type}"
            )

    async def consume(self):
        async for msg in self.consumer:
            key = msg.key
            value = msg.value

            if key is None:
                event = self.serializer.deserialize_event(value)
                key = event.event_id
            else:
                event = None
                key = msg.key().decode("utf-8")

            if key in self.futures.keys():
                if not event:
                    event = self.serializer.deserialize_event(value)
                future = self.futures[key]
                future[1].set_result(self.parse_result(event, future[0]))
                del self.futures[key]

    async def send(self, event: Event, return_type: T):
        producer: AIOKafkaProducer = self.producer
        await producer.send_and_wait(
            self.req_topic,
            bytes(self.serializer.serialize_event(event), "utf-8"),
            bytes(event.event_id, "utf-8"),
        )

        future: Future = self.loop.create_future()
        self.futures[event.event_id] = (return_type, future)

        return future

    async def close(self):
        await self.producer.stop()
        await self.consumer.stop()
