from stateflow.serialization.serde import SerDe, Dict
from stateflow.dataflow.address import FunctionAddress, FunctionType
from stateflow.dataflow.event import Event, EventType
from stateflow.dataflow.state import State
from stateflow.dataflow.event_flow import EventFlowGraph
from stateflow.serialization.proto import event_pb2
from typing import Tuple
import pickle


class ProtoSerializer(SerDe):
    def event_to_proto(self, event: Event) -> event_pb2.Event:
        proto_event: event_pb2.Event = event_pb2.Event()

        # Set id.
        proto_event.event_id = event.event_id
        proto_event.fun_address.key = (
            event.fun_address.key if event.fun_address.key else ""
        )
        proto_event.fun_address.fun_type.namespace = (
            event.fun_address.function_type.namespace
        )
        proto_event.fun_address.fun_type.name = event.fun_address.function_type.name
        proto_event.fun_address.fun_type.stateful = (
            event.fun_address.function_type.stateful
        )

        # Set event type.
        if isinstance(event.event_type, EventType.Request):
            proto_event.request = event_pb2.Request.Value(event.event_type.value)
        elif isinstance(event.event_type, EventType.Reply):
            proto_event.reply = event_pb2.Reply.Value(event.event_type.value)
        else:
            raise AttributeError(f"Unknown event type! {event.event_type}")

        proto_event.payload = pickle.dumps(event.payload)

        # If we're dealing with event flow:
        if event.event_type == EventType.Request.EventFlow:
            flow_graph: EventFlowGraph = event.payload["flow"]
            current_node = flow_graph.current_node
            current_fun: FunctionAddress = current_node.fun_addr

            proto_event.current.current_fun.key = (
                current_fun.key if current_fun.key else ""
            )
            proto_event.current.current_fun.fun_type.namespace = (
                current_fun.function_type.namespace
            )
            proto_event.current.current_fun.fun_type.name = (
                current_fun.function_type.name
            )
            proto_event.current.current_fun.fun_type.stateful = (
                current_fun.function_type.stateful
            )
            proto_event.current.current_node_type = current_node.typ

        return proto_event

    def serialize_event(self, event: Event) -> str:
        proto_event: event_pb2.Event = self.event_to_proto(event)
        return proto_event.SerializeToString()

    def parse_event(self, event: event_pb2.Event) -> Event:
        event_id = event.event_id

        if event.fun_address.key:
            fun_addr = FunctionAddress(
                FunctionType(
                    event.fun_address.fun_type.namespace,
                    event.fun_address.fun_type.name,
                    event.fun_address.fun_type.stateful,
                ),
                event.fun_address.key,
            )
        else:
            fun_addr = FunctionAddress(
                FunctionType(
                    event.fun_address.fun_type.namespace,
                    event.fun_address.fun_type.name,
                    event.fun_address.fun_type.stateful,
                ),
                "",
            )

        # Set event type.
        if event.HasField("request"):
            event_type = EventType.Request[event_pb2.Request.Name(event.request)]
        elif event.HasField("reply"):
            event_type = EventType.Reply[event_pb2.Reply.Name(event.reply)]
        else:
            raise AttributeError(f"Unknown event type! {event.event_type}")

        payload = pickle.loads(event.payload)

        return Event(event_id, fun_addr, event_type, payload)

    def deserialize_event(self, raw_event: bytes) -> Event:
        event: event_pb2.Event = event_pb2.Event()
        event.ParseFromString(raw_event)

        return self.parse_event(event)

    def deserialize_request(self, raw_request: bytes) -> Tuple[Event, State]:
        request: event_pb2.EventRequestReply = event_pb2.EventRequestReply()
        request.ParseFromString(raw_request)

        return self.parse_event(request.event), request.state, request.operator_name

    def serialize_request(self, event: Event, state: bytes) -> bytes:
        request: event_pb2.EventRequestReply = event_pb2.EventRequestReply()
        request.event.CopyFrom(self.event_to_proto(event))
        request.state = state
        request.operator_name = ""

        return request.SerializeToString()

    def serialize_dict(self, dict: Dict) -> bytes:
        return pickle.dumps(dict)

    def deserialize_dict(self, dict: bytes) -> Dict:
        return pickle.loads(dict)
