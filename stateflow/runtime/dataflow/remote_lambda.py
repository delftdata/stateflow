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
import time


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
        start = time.perf_counter()
        parsed_event, state, operator_name = self.serializer.deserialize_request(
            base64.b64decode(event["request"])
        )
        end = time.perf_counter()
        time_ms = (end - start) * 1000
        current_operator: StatefulOperator = self.operators[operator_name]

        current_experiment_data = {
            "STATE_SERIALIZATION_DURATION": parsed_event.stats[
                "STATE_SERIALIZATION_DURATION"
            ],
            "EVENT_SERIALIZATION_DURATION": parsed_event.stats[
                "EVENT_SERIALIZATION_DURATION"
            ],
            "ROUTING_DURATION": parsed_event.stats["ROUTING"],
            "ACTOR_CONSTRUCTION": parsed_event["ACTOR_CONSTRUCTION"],
            "EXECUTION_GRAPH_TRAVERSAL": parsed_event["EXECUTION_GRAPH_TRAVERSAL"],
            "FLINK": parsed_event["FLINK"],
            "TO_AWS": parsed_event["TO_AWS"],
        }

        current_experiment_data["EVENT_SERIALIZATION_DURATION"] += time_ms

        current_operator.current_experiment_date = current_experiment_data
        current_operator.class_wrapper.current_experiment_date = current_experiment_data

        incoming_time = round(time.time() * 1000) - parsed_event.stats.pop(
            "INCOMING_TIMESTAMP"
        )

        current_experiment_data["TO_AWS"] += incoming_time

        if (
            parsed_event.event_type == EventType.Request.InitClass
            and not parsed_event.fun_address.key
        ):
            return_event = current_operator.handle_create(parsed_event)
            return_state = state
        else:
            return_event, return_state = current_operator.handle(parsed_event, state)
            return_event = self._handle_return(return_event)

        start = time.perf_counter()
        serialized = self.serializer.serialize_request(return_event, return_state)
        end = time.perf_counter()
        time_ms = (end - start) * 1000

        current_experiment_data["EVENT_SERIALIZATION_DURATION"] += time_ms
        current_experiment_data["OUTGOING_TIMESTAMP"] = round(time.time() * 1000)

        return_event.stats.update(current_experiment_data)

        return {
            "reply": base64.b64encode(
                self.serializer.serialize_request(return_event, return_state)
            ).decode()
        }
