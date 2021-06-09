from typing import List, Optional, Tuple, ByteString, Union
from src.dataflow.event import EventType, Event
from src.dataflow.event_flow import EventFlowGraph, EventFlowNode
from src.dataflow.address import FunctionType
from src.descriptors.class_descriptor import ClassDescriptor
from src.serialization.serde import SerDe
from enum import Enum
from dataclasses import dataclass


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


class RouteDirection(Enum):
    EGRESS = 1
    INTERNAL = 2
    CLIENT = 3


@dataclass
class Route:
    direction: RouteDirection
    route_name: str
    key: str
    value: Union[Event, ByteString]


class EgressRouter:
    def __init__(self, serializer: SerDe, serialize_on_return=True):
        self.serializer = serializer
        self.serialize_on_return = serialize_on_return

    def _route_event_flow(self, event: Event) -> Route:
        flow_graph: EventFlowGraph = event.payload["flow"]
        current_node = flow_graph.current_node

        if current_node.typ == EventFlowNode.RETURN:
            event_id = event.event_id
            event = event.copy(
                event_type=EventType.Reply.SuccessfulInvocation,
                payload={"return_results": current_node.get_results()},
            )
            if self.serialize_on_return:
                event = self.serializer.serialize_event(event)

            return Route(
                RouteDirection.CLIENT,
                "",
                event_id,
                event,
            )
        else:
            event_id = event.event_id
            if self.serialize_on_return:
                event = self.serializer.serialize_event(event)

            return Route(
                RouteDirection.INTERNAL,
                "",
                event_id,
                event,
            )

    def route_and_serialize(self, event: Event) -> Route:
        if event.event_type == EventType.Request.EventFlow:
            return self._route_event_flow(event)
        elif isinstance(event.event_type, EventType.Reply):
            event_id = event.event_id
            if self.serialize_on_return:
                event = self.serializer.serialize_event(event)

            return Route(
                RouteDirection.CLIENT,
                "",
                event_id,
                event,
            )
        else:
            raise AttributeError(
                f"Unknown event type {event.event_type}.\nFull event: {self.serializer.serialize_event(event)}."
            )


class IngressRouter:
    def __init__(self, serializer: SerDe):
        self.serializer = serializer

    def _route_event_flow(self, event: Event) -> Route:
        flow_graph: EventFlowGraph = event.payload["flow"]
        current_node = flow_graph.current_node
        route_name: str = current_node.fun_type.get_full_name()

        if current_node.typ == EventFlowNode.RETURN and current_node.next == -1:
            return Route(
                RouteDirection.EGRESS,
                route_name,
                event.event_id,
                event.copy(
                    event_type=EventType.Reply.SuccessfulInvocation,
                    payload={"return_results": current_node.get_results()},
                ),
            )
        elif current_node.typ == EventFlowNode.REQUEST_STATE:
            print(f"Now requesting state for {current_node.get_request_key()}.")
            key = current_node.get_request_key()
            return Route(RouteDirection.INTERNAL, route_name, key, event)
        elif current_node.typ == EventFlowNode.INVOKE_SPLIT_FUN:
            return Route(
                RouteDirection.INTERNAL, route_name, event.fun_address.key, event
            )
        elif current_node.typ == EventFlowNode.INVOKE_EXTERNAL:
            return Route(RouteDirection.INTERNAL, route_name, current_node.key, event)
        elif current_node.typ == EventFlowNode.INVOKE_CONDITIONAL:
            return Route(
                RouteDirection.INTERNAL, route_name, event.fun_address.key, event
            )
        else:
            raise AttributeError(
                f"Unknown EventFlowNode type in EventFlowGraph {current_node.typ}.\nFull event: {event}."
            )

    def _route_request(self, event: Event, event_type: str) -> Route:
        route_name: str = event.fun_address.function_type.get_full_name()

        if event_type == EventType.Request.EventFlow:
            return self._route_event_flow(event)
        elif event_type == EventType.Request.Ping:
            return Route(
                RouteDirection.EGRESS,
                "",
                event.event_id,
                event.copy(event_type=EventType.Reply.Pong),
            )
        elif event.fun_address.key:
            return Route(
                RouteDirection.INTERNAL, route_name, event.fun_address.key, event
            )
        else:
            return Route(RouteDirection.INTERNAL, route_name, None, event)

    def parse_and_route(self, value: ByteString) -> Route:
        event: Event = self.serializer.deserialize_event(value)
        event_type: EventType = event.event_type

        if not isinstance(event_type, EventType.Request):
            raise AttributeError(
                f"Ingress router can't route an event which is of type: {event_type}\n.Full event: {event}"
            )

        return self._route_request(event, event_type)


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

    def get_descriptor_by_type(
        self, function_type: FunctionType
    ) -> Optional[ClassDescriptor]:
        get_operator = [
            op.class_wrapper.class_desc
            for op in self.operators
            if op.function_type == function_type
        ]

        if len(get_operator) == 0:
            return None

        return get_operator[0]
