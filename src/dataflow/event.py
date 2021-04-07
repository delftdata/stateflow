from src.descriptors import ClassDescriptor
from src.dataflow import Arguments
from typing import List, Optional
from enum import Enum
import ujson


class FunctionType:
    __slots__ = "namespace", "name", "stateful"

    def __init__(self, namespace: str, name: str, stateful: bool):
        self.namespace = namespace
        self.name = name
        self.stateful = stateful

    def is_stateless(self):
        return not self.stateful

    def __eq__(self, other):
        if not isinstance(other, FunctionType):
            return False

        namespace_eq = self.namespace == other.namespace
        name_eq = self.name == other.name
        stateful_eq = self.stateful == other.stateful

        return namespace_eq and name_eq and stateful_eq

    def to_dict(self):
        return {
            "namespace": self.namespace,
            "name": self.name,
            "stateful": self.stateful,
        }

    @staticmethod
    def create(desc: ClassDescriptor) -> "FunctionType":
        name = desc.class_name
        namespace = "global"  # for now we have a global namespace
        stateful = True  # for now we only cover stateful functions

        return FunctionType(namespace, name, stateful)


class FunctionAddress:
    """The address of a stateful or stateless function.

    Consists of two parts:
    - a FunctionType: the namespace and name of the function, and a flag to specify it as stateful
    - a key: an optional key, in case we deal with a stateful function.

    This address can be used to route an event correctly through a dataflow.
    """

    __slots__ = "function_type", "key"

    def __init__(self, function_type: FunctionType, key: Optional[str]):
        self.function_type = function_type
        self.key = key

    def is_stateless(self):
        return self.function_type.is_stateless()

    def to_dict(self):
        return {"function_type": self.function_type.to_dict(), "key": self.key}


class _Request(Enum):
    InvokeStateless = "InvokeStateless"
    InvokeStateful = "InvokeStateful"
    InitClass = "InitClass"

    GetState = "GetState"
    SetState = "SetState"
    UpdateState = "UpdateState"
    DeleteState = "DeleteState"


class _Reply(Enum):
    SuccessfulInvocation = "SuccessfulInvocation"
    SuccessfulCreateClass = "SuccessfulCreateClass"
    FailedInvocation = "FailedInvocation"


class EventType(Enum):
    Request = _Request
    Reply = _Reply


class Event:
    def __init__(
        self,
        event_id: str,
        fun_address: FunctionAddress,
        event_type: EventType,
        args: Optional[Arguments],
    ):
        self.event_id: str = event_id
        self.fun_address: FunctionAddress = fun_address
        self.event_type: EventType = event_type
        self.arguments: Optional[Arguments] = args

    @staticmethod
    def serialize(event: "Event") -> str:
        function_addr = event.fun_address.to_dict()

        return ujson.dumps(
            {
                "event_id": event.event_id,
                "function_addr": function_addr,
                "event_type": event.event_type.value,
                "event_args": event.arguments.get(),
            }
        )

    @staticmethod
    def deserialize(event_serialized: str) -> "Event":
        json = ujson.load(event_serialized)

        event_id = json["event_id"]
        function_addr = FunctionAddress(
            FunctionType(
                json["function_addr"]["function_type"]["namespace"],
                json["function_addr"]["function_type"]["name"],
                json["function_addr"]["function_type"]["stateful"],
            ),
            json["function_addr"]["key"],
        )
        event_type = json["event_type"]
        args = json["event_args"]

        return Event(event_id, function_addr, event_type, Arguments(args))
