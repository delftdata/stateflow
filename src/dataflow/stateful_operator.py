from src.dataflow import Operator
from src.descriptors import ClassDescriptor
from typing import NewType, List

NoType = NewType("NoType", None)


class StatefulOperator(Operator):
    def __init__(
        self,
        incoming_edges: List["Edge"],
        outgoing_edges: List["Edge"],
        class_descriptor: ClassDescriptor,
    ):
        super().__init__(incoming_edges, outgoing_edges)
        self.class_descriptor = class_descriptor
