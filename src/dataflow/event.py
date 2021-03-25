from src.dataflow.state import State
from src.dataflow.args import Arguments
from typing import List


class Event:
    def __init__(
        self,
        class_name: str,
        class_key: str,
        func_name: str,
        state: State,
        args: Arguments,
    ):
        self.class_name = class_name
        self.class_key = class_key
        self.fun_name = func_name
        self.state = state
        self.arguments = args
