from src.dataflow.state import State
from src.dataflow.args import Arguments
from typing import List, Optional


class FunctionAddress:
    """The address of a stateful or stateless function.

    Consists of two parts:
    - a FunctionType: the namespace and name of the function, and a flag to specify it as stateful
    - a key: an optional key, in case we deal with a stateful function.

    This address can be used to route an event correctly through a dataflow.
    """

    class FunctionType:
        def __init__(self, namespace: str, name: str, stateful: bool):
            self.namespace = namespace
            self.name = name
            self.stateful = stateful

        def is_stateless(self):
            return not self.stateful

    def __init__(self, function_type: FunctionType, key: Optional[str]):
        self.function_type = function_type
        self.key = key

    def is_stateless(self):
        return self.function_type.is_stateless()


class Event:
    def __init__(self, fun_address: FunctionAddress, args: Arguments):
        self.fun_address = fun_address
        self.arguments = args
