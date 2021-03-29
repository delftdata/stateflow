from typing import List
from src.dataflow.event import Event, EventType
from src.descriptors import ClassDescriptor


class Operator:
    def __init__(self, incoming_edges: List["Edge"], outgoing_edges: List["Edge"]):
        self.incoming_edges = incoming_edges
        self.outgoing_edges = outgoing_edges


class Edge:
    def __init__(
        self, from_operator: Operator, to_operator: Operator, event_type: EventType
    ):
        self.from_operator = from_operator
        self.to_operator = to_operator
        self.event_type = event_type


class Ingress(Edge):
    def __init__(
        self, from_operator: "Operator", to_operator: "Operator", event_type: EventType
    ):
        super().__init__(from_operator, to_operator, event_type)


class Egress(Edge):
    def __init__(
        self, from_operator: "Operator", to_operator: "Operator", event_type: EventType
    ):
        super().__init__(from_operator, to_operator, event_type)


class Dataflow:
    def __init__(self, operators: List[Operator], edges: List[Edge]):
        self.operators = operators
        self.edges = edges

    def get_ingresses(self) -> List[Ingress]:
        return [edge for edge in self.edges if isinstance(edge, Ingress)]

    def get_egresses(self) -> List[Egress]:
        return [edge for edge in self.edges if isinstance(edge, Egress)]
