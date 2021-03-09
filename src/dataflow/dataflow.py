from typing import List


class Event:
    def __init__(
        self,
        event_name: str,
        argument_state: dict,
        operator_state: dict,
        hidden_state: dict,
    ):
        self.event_name = event_name
        self.argument_state = argument_state
        self.operator_state = operator_state
        self.hidden_state = hidden_state


class Operator:
    def __init__(
        self,
        name: str,
        incoming_edges: List["Edge"],
        outgoing_edges: List["Edge"],
        input_event_name: str,
        output_event_name: str,
    ):
        self.name = name
        self.incoming_edges = incoming_edges
        self.outgoing_edges = outgoing_edges

        self.input_event_name = input_event_name
        self.output_event_name = output_event_name

        for edge in incoming_edges:
            if edge.get_event().event_name != self.input_event_name:
                raise AttributeError(
                    f"Operator {name} only accepts incoming edges with events of type {input_event_name}, but got an edge of type {edge.get_event().event_name}."
                )

        for edge in outgoing_edges:
            if edge.get_event().event_name != self.input_event_name:
                raise AttributeError(
                    f"Operator {name} only accepts outgoing edges with events of type {output_event_name}, but got an edge of type {edge.get_event().event_name}."
                )

    def init_operator(self):
        pass

    def invoke(self, event: Event) -> Event:
        if self.input_event_name != event.event_name:
            raise AttributeError(
                f"Expected an {self.input_event_name} event to invoke {self.name}, but got an {event.event_name} event."
            )

        print(f"Invoked {self.name}.")
        # Actually call the function here.

        output_event = Event(self.output_event_name, None, None, None)
        return output_event


class StateOperator(Operator):
    def init_operator(self):
        pass


class Edge:
    def __init__(self, from_operator: Operator, to_operator: Operator, event_name: str):
        self.from_operator = from_operator
        self.to_operator = to_operator
        self.event_name = event_name

    def get_event(self) -> Event:
        return self.event

    def flow(self, event: Event) -> List[Event]:
        output_event: Event = self.to_operator.invoke(event)

        if len(self.to_operator.outgoing_edges) == 0:
            return [output_event]

        outputs = []
        for edge in self.to_operator.outgoing_edges:
            outputs = outputs + edge.flow(output_event)

        return outputs


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
