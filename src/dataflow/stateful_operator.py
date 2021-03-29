from src.dataflow import Operator, Edge, FunctionType
from src.wrappers import ClassWrapper
from typing import NewType, List

NoType = NewType("NoType", None)


class StatefulOperator(Operator):
    def __init__(
        self,
        incoming_edges: List[Edge],
        outgoing_edges: List[Edge],
        function_type: FunctionType,
        class_wrapper: ClassWrapper,
    ):
        super().__init__(incoming_edges, outgoing_edges, function_type)
        self.class_wrapper = class_wrapper
