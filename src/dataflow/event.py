from src.wrappers import ClassWrapper
from src.dataflow import Arguments
from typing import List, Optional
from enum import Enum


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

    @staticmethod
    def create(wrapper: ClassWrapper) -> "FunctionType":
        name = wrapper.class_desc.class_name
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


class _Request(Enum):
    InvokeStateless = "InvokeStateless"
    InvokeStateful = "InvokeStateful"

    GetState = "GetState"
    SetState = "SetState"
    UpdateState = "UpdateState"
    DeleteState = "DeleteState"


class _Reply(Enum):
    SuccessfulInvocation = "SuccessfulInvocation"
    FailedInvocation = "FailedInvocation"


class EventType(Enum):
    Request = _Request
    Reply = _Reply


class Event:
    def __init__(
        self, fun_address: FunctionAddress, event_type: EventType, args: Arguments
    ):
        self.fun_address = fun_address
        self.event_type = event_type
        self.arguments = args
