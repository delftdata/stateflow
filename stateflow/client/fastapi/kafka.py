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
    Dict,
)
from stateflow.dataflow.dataflow import IngressRouter
from aiokafka.helpers import create_ssl_context
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
        statefun_mode: bool = False,
        producer_config: Dict = {},
        consumer_config: Dict = {},
    ):
        super().__init__(flow, serializer, timeout, root)

        self.producer: AIOKafkaProducer = None
        self.consumer: AIOKafkaConsumer = None

        self.producer_config = producer_config
        self.consumer_config = consumer_config

        self.statefun_mode: bool = statefun_mode

        if self.statefun_mode:
            self.ingress_router = IngressRouter(self.serializer)

    def setup_init(self):
        super().setup_init()

        @self.app.on_event("startup")
        async def setup_kafka():
            if "bootstrap_servers" not in self.producer_config:
                self.producer_config["bootstrap_servers"] = "localhost:9092"

            self.producer = AIOKafkaProducer(
                ssl_context=create_ssl_context(), **self.producer_config
            )
            await self.producer.start()

            if "bootstrap_servers" not in self.consumer_config:
                self.producer_config["bootstrap_servers"] = "localhost:9092"

            if "group_id" not in self.consumer_config:
                self.producer_config["group_id"] = str(uuid.uuid4())

            if "auto_offset_reset" not in self.consumer_config:
                self.producer_config["auto_offset_reset"] = "latest"

            self.consumer = AIOKafkaConsumer(
                "client_reply",
                ssl_context=create_ssl_context(),
                loop=asyncio.get_event_loop(),
                **self.consumer_config
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
            if msg.key and msg.key.decode("utf-8") not in self.request_map:
                continue

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

        if not self.statefun_mode:
            await self.producer.send_and_wait(
                "client_request", self.serializer.serialize_event(event)
            )
        elif event.event_type == EventType.Request.Ping:
            await self.producer.send_and_wait(
                "globals_ping",
                self.serializer.serialize_event(event),
                key=bytes(event.event_id, "utf-8"),
            )
        else:
            route = self.ingress_router.route(event)
            topic = route.route_name.replace("/", "_")
            key = route.key or event.event_id

            if not route.key:
                topic = topic + "_create"

            await self.producer.send_and_wait(
                topic,
                value=self.serializer.serialize_event(event),
                key=bytes(key, "utf-8"),
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
        if not self.statefun_mode:
            await self.producer.send_and_wait(
                "client_request", self.serializer.serialize_event(event)
            )
        else:
            route = self.ingress_router.route(event)
            topic = route.route_name.replace("/", "_")
            key = route.key or event.event_id

            if not route.key:
                topic = topic + "_create"

            await self.producer.send_and_wait(
                topic,
                value=self.serializer.serialize_event(event),
                key=bytes(key, "utf-8"),
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
