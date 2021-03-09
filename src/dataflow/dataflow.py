from typing import List


class Operator:
    pass


class Event:
    def __init__(
        self,
        event_name: str,
        event_state: dict,
        operator_state: dict,
        hidden_state: dict,
    ):
        self.event_name = event_name
        self.event_state = event_state
        self.operator_state = operator_state
        self.hidden_state = hidden_state


class Edge:
    def __init__(self, from_operator: Operator, to_operator: Operator, event: Event):
        self.from_operator = from_operator
        self.to_operator = to_operator
        self.event = event


class Ingress:
    pass


class Egress:
    pass


class Dataflow:
    def __init__(
        self,
        operators: List[Operator],
        edges: List[Edge],
        ingresses: List[Ingress],
        egresses: List[Egress],
    ):
        self.operators = operators
        self.edges = edges
        self.ingresses = ingresses
        self.egresses = egresses
