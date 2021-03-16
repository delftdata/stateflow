from state import State
from typing import List


class Event:
    def __init__(
        self,
        func_name: str,
        operator_id: str,
        invocation_arguments,
        hidden_state: List[State],  # Maybe a list of hidden state?
    ):
        pass
