from src.dataflow.dataflow import Operator, Edge, FunctionType
from src.dataflow.event import Event
from src.dataflow.state import State
from src.wrappers import ClassWrapper, MetaWrapper
from typing import NewType, List, Tuple

NoType = NewType("NoType", None)


class StatefulOperator(Operator):
    def __init__(
        self,
        incoming_edges: List[Edge],
        outgoing_edges: List[Edge],
        function_type: FunctionType,
        class_wrapper: ClassWrapper,
        meta_wrapper: MetaWrapper,
    ):
        super().__init__(incoming_edges, outgoing_edges, function_type)
        self.class_wrapper = class_wrapper
        self.meta_wrapper = meta_wrapper

    def handle(self, event: Event, state: State) -> Tuple[Event, State]:
        print(f"Now handling event {event}, with state {state}")
        result = self.class_wrapper.init_class(event.arguments)
        return event, result.updated_state
