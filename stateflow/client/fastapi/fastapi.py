import asyncio

from fastapi import FastAPI, Request, Depends, Query
from stateflow.dataflow.dataflow import Dataflow, ClassDescriptor
from stateflow.descriptors.method_descriptor import MethodDescriptor
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
    def __init__(
        self,
        flow: Dataflow,
        serializer: SerDe = PickleSerializer(),
        timeout: int = 5,
        root: str = "stateflow",
    ):
        self.app: FastAPI = FastAPI()
        self.serializer: SerDe = serializer
        self.request_map: Dict[str, StateflowFuture] = {}

        self.root = root if not root else f"/{root}/"

        self.class_descriptors: Dict[str, ClassDescriptor] = {}
        self.timeout: int = timeout
        self.setup_init()

        for operator in flow.operators:
            operator.meta_wrapper.to_asynchronous_wrapper()
            operator.meta_wrapper.set_client(self)

            cls_descriptor: ClassDescriptor = operator.class_wrapper.class_desc
            self.class_descriptors[cls_descriptor.class_name] = cls_descriptor

            fun_type = operator.function_type

            for method in cls_descriptor.methods_dec:
                if not self.get_name(method) == "__key__":
                    self.create_method_endpoint(fun_type, method, cls_descriptor)

            self.create_find_endpoint(fun_type)

    def setup_init(self):
        @self.app.get("/")
        async def default_root():
            return "Welcome to the FastAPI Stateflow client."

        @self.app.get(f"{self.root}ping")
        async def send_ping():
            event = Event(
                str(uuid.uuid4()),
                FunctionAddress(FunctionType("", "", False), None),
                EventType.Request.Ping,
                {},
            )
            future = StateflowFuture(
                event.event_id, time.time(), event.fun_address, None
            )

            # Send event, completing the future.
            await self.send_and_wait_with_future(event, future, "Ping timed out..")

            try:
                future.get()
            except StateflowFailure as fail:
                return fail.error_msg

            return "Pong"

    async def send_and_wait_with_future(
        self,
        event: Event,
        future: StateflowFuture,
        timeout_msg: str = "Event timed out.",
    ):
        raise NotImplementedError("Needs to be implemented by subclass.")

    def get_name(self, method: MethodDescriptor) -> str:
        """Gets the name of the method.

        When a method is named '__init__', 'create' is returned.

        :param method: the MethodDescriptor.
        :return: the name of the method.
        """
        if method.method_name == "__init__":
            return "create"
        return method.method_name

    def create_find_endpoint(self, function_type: FunctionType):
        """Creates the endpoint for finding a stateful function instance.

        For example:
        http://localhost/stateflow/global/User/find?key=john

        This queries the runtime if the global/User with key=john exists.

        Currently, only an acknowledgement is returned whether or not an instance exists.
        In other words, state is not in the return result.

        :param function_type: the type of the stateful funtion endpoint to create.
        :return: the 'find' endpoint.
        """

        @self.app.get(
            f"{self.root}{function_type.get_full_name()}/find/",
            name=f"find_{function_type.get_full_name()}",
        )
        async def endpoint(key: str):
            event = Event(
                str(uuid.uuid4()),
                FunctionAddress(function_type, key),
                EventType.Request.FindClass,
                {},
            )
            future = StateflowFuture(
                event.event_id, time.time(), event.fun_address, None
            )

            # Send and 'fill' the future.
            await self.send_and_wait_with_future(
                event, future, f"Finding {key} timed out after {self.timeout} seconds."
            )

            # Catch the potential exception and return the result.
            try:
                result = future.get()
            except StateflowFailure:
                return (
                    f"{function_type.get_full_name()} with key = {key} does not exist."
                )

            return result

        return endpoint

    def create_flow_event(
        self, flow: List[EventFlowNode], fun_addr: FunctionAddress, args: Arguments
    ) -> Event:
        payload = {
            "flow": EventFlowGraph.construct_and_assign_arguments(flow, fun_addr, args)
        }
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
        else:  # We expect a singleton and it is not explicitly checked. Currently we only support List or 'singletons'.
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

    def create_method_endpoint(
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

            if method_desc.method_name == "__init__":
                args = f"""
class {self.get_name(method_desc)}_params:
    def __init__(self,{input_args}):
        {input_assign}
            """
            else:
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
            else:
                key = None

            payload = {"args": Arguments(args)}
            event_id: str = str(uuid.uuid4())

            if is_init:
                event = Event(
                    event_id,
                    FunctionAddress(class_desc.to_function_type(), key),
                    EventType.Request.InitClass,
                    payload,
                )
            elif is_flow:
                event = self.create_flow_event(
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

            future = StateflowFuture(
                event.event_id, time.time(), event.fun_address, event.fun_address.key
            )

            # Send and 'fill' the future.
            await self.send_and_wait_with_future(
                event, future, f"Finding {key} timed out after {self.timeout} seconds."
            )

            # Catch the potential exception and return the result.
            try:
                result = future.get()
            except StateflowFailure as exc:
                return exc.error_msg

            return result

        return endpoint

    async def send(self, event: Event, return_type: T = None):
        raise NotImplementedError("Needs to be implemented by subclass.")

    def get_app(self) -> FastAPI:
        return self.app
