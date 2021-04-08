from src.dataflow import FunctionAddress
from src.descriptors import ClassDescriptor, MethodDescriptor
from src.client.future import StateflowFuture
from src.dataflow.args import Arguments
from src.dataflow.event import Event, EventType
from src.client.stateflow_client import StateflowClient
import uuid


class MethodRef:
    def __init__(
        self, method_name: str, class_ref: "ClassRef", method_desc: MethodDescriptor
    ):
        self.method_name = method_name
        self._class_ref = class_ref
        self.method_desc = method_desc

    def __call__(self, *args, **kwargs) -> StateflowFuture:
        print(
            f"Now invoking method: {self.method_name}, with arguments: {args} and {kwargs}."
        )

        return self._class_ref.invoke_method(
            self.method_name,
            Arguments.from_args_and_kwargs(
                self.method_desc.input_desc.get(), *args, **kwargs
            ),
        )


class ClassRef:
    def __init__(
        self,
        fun_addr: FunctionAddress,
        class_desc: ClassDescriptor,
        client: StateflowClient,
    ):
        self._fun_addr = fun_addr
        self._class_desc = class_desc
        self._attributes = list(class_desc.state_desc.get_keys())
        self._methods = {
            method.method_name: method for method in class_desc.methods_dec
        }
        self._client = client

    def invoke_method(self, method_name: str, args: Arguments) -> StateflowFuture:
        payload = {"args": args, "method_name": method_name}
        event_id: str = str(uuid.uuid4())

        invoke_method_event = Event(
            event_id, self._fun_addr, EventType.Request.InvokeStateful, payload
        )

        return self._client.send(invoke_method_event)

    def get_attribute(self, attr: str) -> StateflowFuture:
        pass

    def set_attribute(self, attr: str, new) -> StateflowFuture:
        pass

    def __getattr__(self, item):
        if item in self._attributes:
            print(f"Attribute access: {item}")

        if item in self._methods.keys():
            print(f"Method invocation: {item}")
            return MethodRef(item, self, self._methods[item])

    def __str__(self):
        return f"Class reference for {self._fun_type.name}."
