from src.dataflow.state import State
from src.dataflow.args import Arguments
from typing import List, Optional


class FunctionAddress:
    """The address of a stateful or stateless function.

    Consists of two parts:
    - a FunctionType: the namespace and name of the function
    - a key: an optional key, in case we deal with a stateful function.
    For a stateless function, this key is None.

    This address can be used to route an event correctly through a dataflow.
    """

    class FunctionType:
        def __init__(self, namespace: str, name: str):
            self.namespace = namespace
            self.name = name

    def __init__(self, function_type: FunctionType, key: Optional[str]):
        self.function_type = function_type
        self.key = key

    def is_stateless(self):
        return self.key is None


class Event:
    def __init__(self, fun_address: FunctionAddress, args: Arguments):
        self.fun_address = fun_address
        self.arguments = args
