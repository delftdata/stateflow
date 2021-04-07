from src.descriptors import ClassDescriptor
from src.dataflow import Arguments
from typing import List, Optional, Dict
from enum import Enum, EnumMeta
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

    def to_dict(self) -> Dict:
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

    @staticmethod
    def from_dict(dictionary: Dict) -> "FunctionAddress":
        return FunctionAddress(
            FunctionType(
                dictionary["function_type"]["namespace"],
                dictionary["function_type"]["name"],
                dictionary["function_type"]["stateful"],
            ),
            dictionary["key"],
        )


class MetaEnum(EnumMeta):
    def __contains__(cls, item):
        try:
            cls(item)
        except ValueError:
            return False
        return True


class _Request(Enum, metaclass=MetaEnum):
    InvokeStateless = "InvokeStateless"
    InvokeStateful = "InvokeStateful"
    InitClass = "InitClass"

    GetState = "GetState"
    SetState = "SetState"
    UpdateState = "UpdateState"
    DeleteState = "DeleteState"


class _Reply(Enum, metaclass=MetaEnum):
    SuccessfulInvocation = "SuccessfulInvocation"
    SuccessfulCreateClass = "SuccessfulCreateClass"
    FailedInvocation = "FailedInvocation"

    def __contains__(cls, item):
        try:
            cls(item)
        except ValueError:
            return False
        return True


class EventType:
    Request = _Request
    Reply = _Reply

    @staticmethod
    def from_str(input_str: str) -> Optional["EvenType"]:
        if input_str in EventType.Request:
            return EventType.Request[input_str]
        elif input_str in EventType.Reply:
            return EventType.Reply[input_str]
        else:
            return None


class Event:
    def __init__(
        self,
        event_id: str,
        fun_address: FunctionAddress,
        event_type: EventType,
        payload: Dict,
    ):
        self.event_id: str = event_id
        self.fun_address: FunctionAddress = fun_address
        self.event_type: EventType = event_type
        self.payload = payload

        # self.arguments: Optional[Arguments] = args

    def get_arguments(self) -> Optional[Arguments]:
        if "args" in self.payload:
            return self.payload["args"]
        else:
            return None

    @staticmethod
    def serialize(event: "Event") -> str:
        function_addr = event.fun_address.to_dict()

        if event.arguments == None:
            args = None
        else:
            args = event.arguments.get()

        return ujson.dumps(
            {
                "event_id": event.event_id,
                "function_addr": function_addr,
                "event_type": event.event_type.value,
                "event_args": args,
            }
        )

    @staticmethod
    def deserialize(event_serialized: str) -> "Event":
        json = ujson.decode(event_serialized)

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
