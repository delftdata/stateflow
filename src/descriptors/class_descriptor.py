from src.dataflow.state import StateDescriptor
from typing import List
from src.descriptors import MethodDescriptor


class ClassDescriptor:
    """A description of a class method."""

    def __init__(
        self,
        class_name: str,
        state_desc: StateDescriptor,
        methods_dec: List[MethodDescriptor],
    ):
        self.class_name: str = class_name
        self.state_desc: StateDescriptor = state_desc
        self.methods_dec: List[MethodDescriptor] = methods_dec
