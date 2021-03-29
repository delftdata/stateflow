from typing import List, Optional
from src.dataflow.event import EventType, FunctionType


class Operator:
    def __init__(
        self,
        incoming_edges: List["Edge"],
        outgoing_edges: List["Edge"],
        function_type: FunctionType,
    ):
        self.incoming_edges = incoming_edges
        self.outgoing_edges = outgoing_edges
        self.function_type = function_type


class Edge:
    def __init__(
        self,
        from_operator: Optional[Operator],
        to_operator: Optional[Operator],
        event_type: EventType,
    ):
        self.from_operator = from_operator
        self.to_operator = to_operator
        self.event_type = event_type


class Ingress(Edge):
    def __init__(self, name: str, to_operator: "Operator", event_type: EventType):
        super().__init__(None, to_operator, event_type)
        self.name = name


class Egress(Edge):
    def __init__(self, name: str, from_operator: "Operator", event_type: EventType):
        super().__init__(from_operator, None, event_type)
        self.name = name


class Dataflow:
    def __init__(self, operators: List[Operator], edges: List[Edge]):
        self.operators = operators
        self.edges = edges

    def get_ingresses(self) -> List[Ingress]:
        return [edge for edge in self.edges if isinstance(edge, Ingress)]

    def get_egresses(self) -> List[Egress]:
        return [edge for edge in self.edges if isinstance(edge, Egress)]
