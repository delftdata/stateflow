from src.dataflow.dataflow import Operator, Edge, FunctionType, EventType
from src.dataflow.event import Event, EventFlowNode
from src.dataflow.args import Arguments
from src.dataflow.state import State
from src.wrappers import ClassWrapper, MetaWrapper, InvocationResult, FailedInvocation
from typing import NewType, List, Tuple, Optional
from src.serialization.json_serde import SerDe, JsonSerializer

NoType = NewType("NoType", None)


class InternalClassRef:
    def __init__(self, key: str, attributes):
        self.__key = key
        self.__attributes = attributes

        for n, attr in attributes.items():
            setattr(self, n, attr)


class StatefulOperator(Operator):
    def __init__(
        self,
        incoming_edges: List[Edge],
        outgoing_edges: List[Edge],
        function_type: FunctionType,
        class_wrapper: ClassWrapper,
        meta_wrapper: MetaWrapper,
        serializer: SerDe = JsonSerializer(),
    ):
        super().__init__(incoming_edges, outgoing_edges, function_type)
        self.class_wrapper = class_wrapper
        self.meta_wrapper = meta_wrapper
        self.serializer = serializer

    def handle_create(self, event: Event) -> Event:
        res: InvocationResult = self.class_wrapper.init_class(event.payload["args"])

        key: str = res.return_results[0]
        created_state: State = res.updated_state

        event.fun_address.key = key
        event.payload["init_class_state"] = created_state.get()

        return event

    def handle(self, event: Event, state: Optional[bytes]) -> Tuple[Event, bytes]:
        if state is not None:
            state = State(self.serializer.deserialize_dict(state))

        updated_state = None
        return_event = None

        # initialize class
        if event.event_type == EventType.Request.InitClass:
            new_state = event.payload["init_class_state"]

            if state is not None:
                return_event = event.copy(
                    event_type=EventType.Reply.FailedInvocation,
                    payload={
                        "error_message": f"{event.fun_address.function_type.get_full_name()} class "
                        f"with key={event.fun_address.key} already exists."
                    },
                )
            else:
                return_event = event.copy(
                    event_type=EventType.Reply.SuccessfulCreateClass,
                    payload={"key": f"{event.fun_address.key}"},
                )
                updated_state = State(new_state)

        elif event.event_type == EventType.Request.InvokeStateful:
            invocation: InvocationResult = self.class_wrapper.invoke(
                event.payload["method_name"], state, event.payload["args"]
            )

            if isinstance(invocation, FailedInvocation):
                return_event = event.copy(
                    event_type=EventType.Reply.FailedInvocation,
                    payload={"error_message": invocation.message},
                )
            else:
                return_event = event.copy(
                    event_type=EventType.Reply.SuccessfulInvocation,
                    payload={"return_results": invocation.return_results},
                )
                updated_state = invocation.updated_state
        elif event.event_type == EventType.Request.GetState:
            if state == None:  # class does not exist
                return event, state
            return_event = event.copy(
                event_type=EventType.Reply.SuccessfulStateRequest,
                payload={"state": state[event.payload["attribute"]]},
            )
            updated_state = state

        elif event.event_type == EventType.Request.UpdateState:
            if state == None:  # class does not exist
                return event, state
            state[event.payload["attribute"]] = event.payload["attribute_value"]
            return_event = event.copy(
                event_type=EventType.Reply.SuccessfulStateRequest,
                payload={},
            )
            updated_state = state
        elif event.event_type == EventType.Request.FindClass:
            if state == None:  # class does not exist
                return event, state

            updated_state = state
            return_event = event.copy(event_type=EventType.Reply.FoundClass)
        elif event.event_type == EventType.Request.EventFlow:
            current_flow_node_id = event.payload["current_flow"]
            current_node = event.payload["flow"][current_flow_node_id]

            if current_node["node"].typ == EventFlowNode.REQUEST_STATE:
                state_embedded = state.get()
                state_embedded["__key"] = current_node["node"].input["key"]
                current_node["node"].output[
                    current_node["node"]["var_name"]
                ] = state_embedded
            elif current_node["node"].typ == EventFlowNode.INVOKE_SPLIT_FUN:
                for k, val in current_node["node"].input.items():
                    if "__key" in val:
                        key = val.pop("__key")
                        current_node["node"].input[k] = InternalClassRef(key, val)

                invocation: InvocationResult = self.class_wrapper.invoke(
                    event.payload["fun_name"],
                    state,
                    Arguments(current_node["node"].input),
                )

            current_node["status"] = "FINISHED"

            if not isinstance(current_node["node"].next, list):
                event.payload["current_flow"] = current_node["node"].next
                next_node = event.payload["flow"][current_node["node"].next]["node"]

                for node_output in current_node["node"].output.keys():
                    if node_output in next_node.input:
                        next_node.input[node_output] = current_node["node"].output[
                            node_output
                        ]
            else:
                # if it is a list..
                pass

            updated_state = state
            return_event = event

        if updated_state is not None:
            return return_event, bytes(
                self.serializer.serialize_dict(updated_state.get()), "utf-8"
            )
        return return_event, updated_state
