from typing import List


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

    def get_edge_by_event(self, event: Event) -> Edge:
        edge_list = [edge for edge in self.edges if edge.get_event() == event]

        if len(edge_list) > 1:
            raise AttributeError(
                f"Event {event} is used on multiple edges. That should not be possible."
            )

        return edge_list[0]
