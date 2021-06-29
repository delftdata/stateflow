import asyncio

from fastapi import FastAPI, Request, Depends
from stateflow.dataflow.dataflow import Dataflow, ClassDescriptor
from stateflow.descriptors.method_descriptor import MethodDescriptor
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from stateflow.dataflow.event import Event, EventType
from stateflow.dataflow.event_flow import (
    EventFlowGraph,
    EventFlowNode,
    InternalClassRef,
)
from stateflow.dataflow.args import Arguments
from stateflow.client.future import StateflowFuture, StateflowFailure, T
from stateflow.client.stateflow_client import StateflowClient
from stateflow.dataflow.address import FunctionType, FunctionAddress
import uuid
from stateflow.serialization.pickle_serializer import SerDe, PickleSerializer
from typing import Dict, List, Tuple, Any
import re
import time
import copy


class FastAPIClient(StateflowClient):
    def __init__(self, flow: Dataflow, serializer: SerDe = PickleSerializer()):
        self.app: FastAPI = FastAPI()
        self.producer: AIOKafkaProducer = None
        self.consumer: AIOKafkaConsumer = None
        self.serializer: SerDe = serializer
        self.request_map: Dict[str, StateflowFuture] = {}

        self.class_descriptors: Dict[str, ClassDescriptor] = {}
        self.timeout: int = 5
        self.setup_init()

        for operator in flow.operators:
            operator.meta_wrapper.to_asynchronous_wrapper()
            operator.meta_wrapper.set_client(self)

            cls_descriptor: ClassDescriptor = operator.class_wrapper.class_desc
            self.class_descriptors[cls_descriptor.class_name] = cls_descriptor

            fun_type = operator.function_type

            for method in cls_descriptor.methods_dec:
                if not self.get_name(method) == "__key__":
                    self.create_method_handler(fun_type, method, cls_descriptor)

            self.create_fun_get(fun_type)

    async def consume_forever(self):
        async for msg in self.consumer:
            return_event: Event = self.serializer.deserialize_event(msg.value)
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
                result = await asyncio.wait_for(fut, timeout=self.timeout)
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

    def _invoke_flow(
        self, flow: List[EventFlowNode], fun_addr: FunctionAddress, args: Arguments
    ) -> Event:

        to_assign = list(args.get_keys())
        flow_for_params: List = []

        # Get the first nodes up and until the first InvokeSplitFun.
        # For example: RequestState, RequestState, InvokeSplitFun.
        for f in flow:
            flow_for_params.append(f)
            if f.typ == EventFlowNode.INVOKE_SPLIT_FUN:
                break

        for f in flow_for_params:
            to_remove = []
            for arg in to_assign:
                arg_value = args[arg]

                if f.typ == EventFlowNode.REQUEST_STATE and f.var_name == arg:
                    f.set_request_key(arg_value._get_key())
                    f.fun_addr.key = arg_value._get_key()
                    to_remove.append(arg)
                elif arg in f.input:
                    f.input[arg] = arg_value
                    to_remove.append(arg)
            to_assign = [el for el in to_assign if el not in to_remove]

        flow_graph = EventFlowGraph(flow[0], flow)
        flow_graph.set_function_address(flow[0], 0, fun_addr)
        flow_graph.step()

        payload = {"flow": flow_graph}
        event_id: str = str(uuid.uuid4())

        invoke_flow_event = Event(
            event_id, fun_addr, EventType.Request.EventFlow, payload
        )

        return invoke_flow_event

    def _type_is_class(self, typ: str) -> Tuple[bool, ClassDescriptor]:
        match = re.compile(r"(?<=\[)(.*?)(?=\])").search(typ)

        if not match:
            match = typ
        else:
            match = match.group(0)

        class_desc = self.class_descriptors.get(match)
        return class_desc is not None, class_desc

    def _replace_with_internal_ref(
        self, typ: str, value: Any
    ) -> Tuple[Any, InternalClassRef]:
        is_class, class_desc = self._type_is_class(typ)

        if not is_class:
            return value

        fun_type = class_desc.to_function_type()
        if isinstance(value, list):
            return [InternalClassRef(FunctionAddress(fun_type, x)) for x in value]
        else:  # We expect a singleton.
            return InternalClassRef(FunctionAddress(fun_type, value))

    def _compute_input_args(self, method_desc: MethodDescriptor) -> str:
        all_args: List[str] = []
        for name, typ in method_desc.input_desc.get().items():
            is_other_stateful_fun, _ = self._type_is_class(typ)

            if is_other_stateful_fun:
                if typ.startswith("List["):
                    all_args.append(f"{name}: List[str] = Query(None)")
                else:  # We assume it is a singleton.
                    all_args.append(f"{name}: str")
            else:
                all_args.append(f"{name}: {typ}")

        return ", ".join(all_args)

    def create_method_handler(
        self, function_type, method_desc: MethodDescriptor, class_desc: ClassDescriptor
    ):
        # TODO transform lists of stateful functins
        if (
            len(method_desc.input_desc.get()) > 0
            or not method_desc.method_name == "__init__"
        ):
            input_args = self._compute_input_args(method_desc)

            input_assign = "\n        ".join(
                [f"self.{k} = {k}" for k, _ in method_desc.input_desc.get().items()]
            )

            args = f"""
class {self.get_name(method_desc)}_params:
    def __init__(self, key: str, {input_args}):
        self.key = key
        {input_assign}
            """
        else:
            args = f"""
class {self.get_name(method_desc)}_params:
    pass
            """

        exec(compile(args, "", mode="exec"), globals(), globals())

        method_name = self.get_name(method_desc)
        is_init: bool = method_desc.method_name == "__init__"
        is_flow: bool = len(method_desc.flow_list) > 0

        @self.app.post(
            f"/stateflow/{function_type.get_full_name()}/{self.get_name(method_desc)}",
            name=self.get_name(method_desc),
        )
        async def endpoint(
            params: f"{method_name}_params" = Depends(),  # noqa: F821
        ):
            args = {}
            for name, typ in method_desc.input_desc.get().items():
                args[name] = self._replace_with_internal_ref(typ, getattr(params, name))

            if not is_init:
                key = params.key

            payload = {"args": Arguments(args)}
            event_id: str = str(uuid.uuid4())

            if is_init:
                event = Event(
                    event_id,
                    FunctionAddress(class_desc.to_function_type(), None),
                    EventType.Request.InitClass,
                    payload,
                )
            elif is_flow:
                event = self._invoke_flow(
                    copy.deepcopy(method_desc.flow_list),
                    FunctionAddress(class_desc.to_function_type(), key),
                    Arguments(args),
                )
            else:
                payload["method_name"] = method_name
                event = Event(
                    event_id,
                    FunctionAddress(class_desc.to_function_type(), key),
                    EventType.Request.InvokeStateful,
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
                result = await asyncio.wait_for(fut, timeout=self.timeout)
            except asyncio.TimeoutError:
                del self.request_map[event.event_id]
                return "Request timed out."

            future.complete(result)

            try:
                result = future.get()
            except StateflowFailure as exc:
                return exc

            return result

        return endpoint

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

    def get_app(self) -> FastAPI:
        return self.app
