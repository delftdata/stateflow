from src.dataflow.dataflow import Operator, Edge, FunctionType, EventType
from src.dataflow.event import Event
from src.dataflow.state import State
from src.wrappers import ClassWrapper, MetaWrapper, InvocationResult
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

    def handle_create(self, event: Event) -> Event:
        res: InvocationResult = self.class_wrapper.init_class(event.arguments)

        key: str = res.return_results[0]
        created_state: State = res.updated_state

        event.fun_address.key = key
        event.arguments.get()["__state"] = created_state.get()

        return event

    def handle(self, event: Event, state: State) -> Tuple[Event, State]:
        print(f"Now handling event {event}, with state {state}")

        updated_state = None

        # initialize class
        if event.event_type == EventType.Request.value.InitClass:
            state = event.arguments["__state"]

            return Event(event.event_id, event.fun_address)
        elif event.event_type == EventType.Request.value.InvokeStateful:
            pass

        return event
