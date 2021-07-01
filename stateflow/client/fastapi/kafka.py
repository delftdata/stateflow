from stateflow.client.fastapi.fastapi import (
    FastAPIClient,
    Dataflow,
    SerDe,
    PickleSerializer,
    Event,
    StateflowFailure,
    StateflowFuture,
    FunctionAddress,
    FunctionType,
    EventType,
    T,
)
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import asyncio
import uuid
import time


class KafkaFastAPIClient(FastAPIClient):
    def __init__(
        self,
        flow: Dataflow,
        serializer: SerDe = PickleSerializer(),
        timeout: int = 5,
        root: str = "stateflow",
    ):
        super().__init__(flow, serializer, timeout, root)

        self.producer: AIOKafkaProducer = None
        self.consumer: AIOKafkaConsumer = None

    def setup_init(self):
        super().setup_init()

        @self.app.on_event("startup")
        async def setup_kafka():
            self.producer = AIOKafkaProducer(bootstrap_servers="localhost:9092")
            await self.producer.start()

            self.consumer = AIOKafkaConsumer(
                "client_reply",
                loop=asyncio.get_event_loop(),
                bootstrap_servers="localhost:9092",
                group_id=str(uuid.uuid4()),
                auto_offset_reset="latest",
            )
            await self.consumer.start()
            asyncio.create_task(self.consume_forever())

        @self.app.on_event("shutdown")
        async def stop_kafka():
            await self.producer.close()

        return setup_kafka

    async def consume_forever(self):
        """Consumes from the Kafka topic.

        :return:
        """
        async for msg in self.consumer:
            return_event: Event = self.serializer.deserialize_event(msg.value)
            if return_event.event_id in self.request_map:
                self.request_map[return_event.event_id].set_result(return_event)
                del self.request_map[return_event.event_id]

    async def send_and_wait_with_future(
        self,
        event: Event,
        future: StateflowFuture,
        timeout_msg: str = "Event timed out.",
    ):
        await self.producer.send_and_wait(
            "client_request", self.serializer.serialize_event(event)
        )

        loop = asyncio.get_running_loop()
        asyncio_future = loop.create_future()

        self.request_map[event.event_id] = asyncio_future

        try:
            result = await asyncio.wait_for(asyncio_future, timeout=self.timeout)
        except asyncio.TimeoutError:
            del self.request_map[event.event_id]
            future.complete_with_failure(timeout_msg)
        else:
            future.complete(result)

    async def send(self, event: Event, return_type: T = None):
        await self.producer.send_and_wait(
            "client_request", self.serializer.serialize_event(event)
        )
        loop = asyncio.get_running_loop()

        fut = loop.create_future()
        future = StateflowFuture(
            event.event_id, time.time(), event.fun_address, return_type
        )

        self.request_map[event.event_id] = fut

        try:
            result = await asyncio.wait_for(fut, timeout=self.timeout)
        except asyncio.TimeoutError:
            del self.request_map[event.event_id]
            raise StateflowFailure("Request timed out!")

        future.complete(result)

        try:
            result = future.get()
        except StateflowFailure as exc:
            return exc

        return result
