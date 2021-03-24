from src.dataflow.state import StateDescription
from typing import List
from src.dataflow.method_descriptor import MethodDescriptor


class ClassDescriptor:
    """A description of a class method."""

    def __init__(
        self,
        class_name: str,
        state_desc: StateDescription,
        methods_dec: List[MethodDescriptor],
    ):
        self.class_name = class_name
        self.state_desc = state_desc
        self.methods_dec = methods_dec
