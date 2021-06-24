import asyncio

from fastapi import FastAPI, Request, Query, Depends
from src.dataflow.dataflow import Dataflow, ClassDescriptor
from src.descriptors.method_descriptor import MethodDescriptor
from src.dataflow.dataflow import Operator
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from src.dataflow.event import Event, FunctionAddress, EventType
from src.dataflow.args import Arguments
from src.client.future import StateflowFuture, StateflowFailure
from src.dataflow.address import FunctionType, FunctionAddress
import uuid
from src.serialization.pickle_serializer import SerDe, PickleSerializer
from typing import Dict
import time


class FastAPIClient:
    def __init__(self, flow: Dataflow, serializer: SerDe = PickleSerializer()):
        self.app: FastAPI = FastAPI()
        self.producer: AIOKafkaProducer = None
        self.consumer: AIOKafkaConsumer = None
        self.serializer: SerDe = serializer
        self.request_map: Dict[str, StateflowFuture] = {}

        self.setup_init()

        for operator in flow.operators:
            cls_descriptor: ClassDescriptor = operator.class_wrapper.class_desc
            fun_type = operator.function_type

            for method in cls_descriptor.methods_dec:
                if not self.get_name(method) == "__key__":
                    self.create_method_handler(fun_type, method, cls_descriptor)

            self.create_fun_get(fun_type)

    async def consume_forever(self):
        async for msg in self.consumer:
            return_event: Event = self.serializer.deserialize_event(msg.value)
            print(f"Received event with id {return_event.event_id}")
            if return_event.event_id in self.request_map:
                self.request_map[return_event.event_id].set_result(return_event)
                del self.request_map[return_event.event_id]

    def setup_init(self):
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

        @self.app.get("/")
        async def default_root():
            return "Welcome to the FastAPI Stateflow client."

        @self.app.get("/stateflow/ping")
        async def send_ping():
            event = Event(
                str(uuid.uuid4()),
                FunctionAddress(FunctionType("", "", False), None),
                EventType.Request.Ping,
                {},
            )
            await self.producer.send_and_wait(
                "client_request", self.serializer.serialize_event(event)
            )

            loop = asyncio.get_running_loop()
            fut = loop.create_future()
            future = StateflowFuture(
                event.event_id, time.time(), event.fun_address, None
            )

            self.request_map[event.event_id] = fut

            try:
                result = await asyncio.wait_for(fut, timeout=5)
            except asyncio.TimeoutError:
                del self.request_map[event.event_id]
                return "Ping timed out..."

            future.complete(result)
            return "Pong"

        return setup_kafka

    def get_name(self, method: MethodDescriptor) -> str:
        if method.method_name == "__init__":
            return "create"
        return method.method_name

    def create_fun_get(self, function_type):
        @self.app.get(
            f"/stateflow/{function_type.get_full_name()}/find/",
            name=f"find_{function_type.get_full_name()}",
        )
        async def endpoint(key: str, request: Request):
            event = Event(
                str(uuid.uuid4()),
                FunctionAddress(function_type, key),
                EventType.Request.FindClass,
                {},
            )

            await self.producer.send_and_wait(
                "client_request", self.serializer.serialize_event(event)
            )

            loop = asyncio.get_running_loop()

            fut = loop.create_future()
            future = StateflowFuture(
                event.event_id, time.time(), event.fun_address, None
            )

            self.request_map[event.event_id] = fut

            try:
                result = await asyncio.wait_for(fut, timeout=5)
            except asyncio.TimeoutError:
                del self.request_map[event.event_id]
                return "Request timed out."

            future.complete(result)

            try:
                result = future.get()
            except StateflowFailure:
                return (
                    f"{function_type.get_full_name()} with key = {key} does not exist."
                )

            return future.get()

        print(endpoint)
        return endpoint

    def is_primitive(self, el: str) -> bool:
        if el in ["str", "int", "bool", "float"]:
            return True

        return False

    def create_method_handler(
        self, function_type, method_desc: MethodDescriptor, class_desc: ClassDescriptor
    ):
        # TODO transform lists of stateful functins
        if len(method_desc.input_desc.get()) > 0:
            input_args = ", ".join(
                [
                    f"{k}: {v}"
                    for k, v in method_desc.input_desc.get().items()
                    if self.is_primitive(v)
                ]
                + [
                    f"{k}: str"
                    for k, v in method_desc.input_desc.get().items()
                    if not self.is_primitive(v)
                ]
            )
            input_assign = "\n        ".join(
                [f"self.{k} = {k}" for k, _ in method_desc.input_desc.get().items()]
            )

            args = f"""
class {self.get_name(method_desc)}_params:
    def __init__(self, {input_args}):
        {input_assign}
            """
        else:
            args = f"""
class {self.get_name(method_desc)}_params:
    pass
            """

        exec(compile(args, "", mode="exec"), globals(), globals())

        method_name = self.get_name(method_desc)

        @self.app.post(
            f"/stateflow/{function_type.get_full_name()}/{self.get_name(method_desc)}",
            name=self.get_name(method_desc),
        )
        async def endpoint(
            request: Request,
            params: f"{method_name}_params" = Depends(),
        ):
            args = {}
            for key in method_desc.input_desc.keys():
                args[key] = getattr(params, key)

            payload = {"args": Arguments(args)}
            event_id: str = str(uuid.uuid4())

            event = Event(
                event_id,
                FunctionAddress(class_desc.to_function_type(), None),
                EventType.Request.InitClass,
                payload,
            )

            await self.producer.send_and_wait(
                "client_request", self.serializer.serialize_event(event)
            )

            loop = asyncio.get_running_loop()

            fut = loop.create_future()
            future = StateflowFuture(
                event.event_id, time.time(), event.fun_address, None
            )

            self.request_map[event.event_id] = fut

            try:
                result = await asyncio.wait_for(fut, timeout=5)
            except asyncio.TimeoutError:
                del self.request_map[event.event_id]
                return "Request timed out."

            future.complete(result)

            try:
                result = future.get()
            except StateflowFailure as exc:
                return exc

            return future.get()

        return endpoint

    def get_app(self) -> FastAPI:
        return self.app
