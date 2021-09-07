import base64

from stateflow.runtime.aws.abstract_lambda import (
    LambdaBase,
    Runtime,
    Dataflow,
    SerDe,
    Event,
    EventType,
    StatefulOperator,
    EventFlowGraph,
    EventFlowNode,
)
import json
from stateflow.serialization.proto.proto_serde import ProtoSerializer


class RemoteLambda(LambdaBase, Runtime):
    def __init__(self, flow: Dataflow, serializer: ProtoSerializer = ProtoSerializer()):
        self.flow: Dataflow = flow
        self.serializer: ProtoSerializer = serializer

        self.operators = {
            operator.function_type.get_full_name(): operator
            for operator in self.flow.operators
        }

    def _handle_return(self, event: Event) -> Event:
        if event.event_type != EventType.Request.EventFlow:
            return event

        flow_graph: EventFlowGraph = event.payload["flow"]
        current_node = flow_graph.current_node

        if current_node.typ != EventFlowNode.RETURN:
            return event

        if not current_node.next:
            return event.copy(
                event_type=EventType.Reply.SuccessfulInvocation,
                payload={"return_results": current_node.get_results()},
            )

        else:
            for next_node_id in current_node.next:
                next_node = flow_graph.get_node_by_id(next_node_id)

                # Get next node and set proper input.
                next_node.input[current_node.return_name] = current_node.get_results()

            return event

    def handle(self, event, context):
        print(event)
        print(base64.b64decode(event["request"]))
        parsed_event, state, operator_name = self.serializer.deserialize_request(
            base64.b64decode(event["request"])
        )
        print(parsed_event)
        print(state)
        print(f"Operator name {operator_name}")
        current_operator: StatefulOperator = self.operators[operator_name]

        if (
            parsed_event.event_type == EventType.Request.InitClass
            and not parsed_event.fun_address.key
        ):
            print(f"init class! {operator_name}")
            return_event = current_operator.handle_create(parsed_event)
            return_state = state
        else:
            print(f"invoke {operator_name}")
            return_event, return_state = current_operator.handle(parsed_event, state)
            return_event = self._handle_return(return_event)

        return {
            "reply": base64.b64encode(
                self.serializer.serialize_request(return_event, return_state)
            ).decode()
        }
