from src.descriptors.class_descriptor import ClassDescriptor
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

    def get_full_name(self):
        return f"{self.namespace}/{self.name}"

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

    FindClass = "FindClass"

    GetState = "GetState"
    SetState = "SetState"
    UpdateState = "UpdateState"
    DeleteState = "DeleteState"

    def __str__(self):
        return f"Request.{self.value}"


class _Reply(Enum, metaclass=MetaEnum):
    SuccessfulInvocation = "SuccessfulInvocation"
    SuccessfulCreateClass = "SuccessfulCreateClass"

    FoundClass = "FoundClass"

    SuccessfulStateRequest = "SuccessfulStateRequest"
    FailedInvocation = "FailedInvocation"

    def __str__(self):
        return f"Reply.{self.value}"


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
    __slots__ = "event_id", "fun_address", "event_type", "payload"

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
        self.payload: Dict = payload

    def get_arguments(self) -> Optional[Arguments]:
        if "args" in self.payload:
            return self.payload["args"]
        else:
            return None

    def copy(self, **kwargs) -> "Event":
        new_args = {}
        for key, value in kwargs.items():
            if key in self.__slots__:
                new_args[key] = value

        for key in self.__slots__:
            if key not in new_args:
                new_args[key] = getattr(self, key)

        return Event(**new_args)
