from src.dataflow.dataflow import Operator, Edge, FunctionType, EventType
from src.dataflow.event import Event, EventFlowNode
from src.dataflow.args import Arguments
from src.dataflow.state import State
from src.wrappers import ClassWrapper, MetaWrapper, InvocationResult, FailedInvocation
from typing import NewType, List, Tuple, Optional
from split.split import InvokeMethodRequest
from src.serialization.json_serde import SerDe, JsonSerializer

NoType = NewType("NoType", None)


class InternalClassRef:
    def __init__(self, key: str, fun_type, attributes):
        self._key = key
        self._fun_type = fun_type
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
            print(f"Now dealing with {event.payload}")
            current_flow_node_id = event.payload["current_flow"]
            current_node = event.payload["flow"][str(current_flow_node_id)]

            print(f"And current_node {current_node}")
            updated_state = state
            return_event = event

            if current_node["node"].typ == EventFlowNode.REQUEST_STATE:
                state_embedded = state.get()
                state_embedded["__key"] = current_node["node"].input["key"]
                current_node["node"].output[
                    current_node["node"].var_name
                ] = state_embedded

                next_node_id = current_node["node"].next[0]
                event.payload["current_flow"] = next_node_id
                next_node = event.payload["flow"][str(next_node_id)]["node"]

                for node_output in current_node["node"].output.keys():
                    if node_output in next_node.input:
                        next_node.input[node_output] = current_node["node"].output[
                            node_output
                        ]
            elif current_node["node"].typ == EventFlowNode.INVOKE_SPLIT_FUN:
                copied_input = current_node["node"].input.copy()
                for k, val in copied_input.items():
                    if isinstance(val, dict) and "__key" in val:
                        key = val.pop("__key")
                        copied_input[k] = InternalClassRef(
                            key,
                            event.payload["flow"][str(current_node["node"].previous)][
                                "node"
                            ].fun_type,
                            val,
                        )

                print(
                    f"Now calling {current_node['node'].fun_name} with state {state.get()} and args {copied_input}"
                )
                invocation: InvocationResult = self.class_wrapper.invoke(
                    current_node["node"].fun_name,
                    state,
                    Arguments(copied_input),
                )

                updated_state = invocation.updated_state

                # For now we have a very stupid check to know which path to take.
                # This needs to be more sophisticated.
                print(invocation)
                print("We got the following results:")
                # We got the following results: (1, <src.dataflow.stateful_operator.InternalClassRef object at 0x13e235ca0>, 1, <src.split.split.InvokeMethodRequest object at 0x13e2b0550>)
                print(invocation.return_results)
                print(type(invocation.return_results))
                if isinstance(invocation.return_results, tuple):
                    for res in invocation.return_results:
                        print(res)
                print("---")
                if (
                    not isinstance(invocation.return_results, tuple)
                    or len(invocation.return_results) == 1
                ):
                    return_node = [
                        event.payload["flow"][str(i)]["node"]
                        for i in current_node["node"].next
                        if event.payload["flow"][str(i)]["node"].typ
                        == EventFlowNode.RETURN
                    ][0]

                    event.payload["current_flow"] = return_node.id
                    return_node.output["0"] = invocation.return_results

                if isinstance(invocation.return_results, tuple):
                    next_node = [
                        event.payload["flow"][str(i)]["node"]
                        for i in current_node["node"].next
                        if event.payload["flow"][str(i)]["node"].typ
                        == EventFlowNode.INVOKE_EXTERNAL
                    ][0]
                    for i, decl in enumerate(
                        sorted(list(current_node["node"].definitions))
                    ):
                        if isinstance(invocation.return_results[i], InternalClassRef):
                            next_node.key = invocation.return_results[
                                i
                            ]._key  # hacky, find another way

                            print(f"now setting next node key {next_node.key}")

                            current_node["node"].output[decl] = {
                                "key": invocation.return_results[i]._key,
                                "fun_type": invocation.return_results[
                                    i
                                ]._fun_type.to_dict(),
                            }
                        else:
                            current_node["node"].output[
                                decl
                            ] = invocation.return_results[i]

                    invoke_method_request_args = invocation.return_results[-1].args
                    i = 0
                    for k, _ in next_node.input.items():
                        next_node.input[k] = invoke_method_request_args[i]
                        i += 1

                    event.payload["current_flow"] = next_node.id

                    print(
                        f"{return_event.payload['flow']['1']['node'].input} | {return_event.payload['flow']['1']['node'].output}"
                    )
                    print(
                        f"{return_event.payload['flow']['2']['node'].input} | {return_event.payload['flow']['2']['node'].output}"
                    )
                    print(
                        f"{return_event.payload['flow']['3']['node'].input} | {return_event.payload['flow']['3']['node'].output}"
                    )
            elif current_node["node"].typ == EventFlowNode.INVOKE_EXTERNAL:
                fun_name = current_node["node"].method
                arguments = {}

                print(state.get())

                for arg_key, input_val in zip(
                    self.class_wrapper.find_method(fun_name).input_desc.keys(),
                    current_node["node"].input.values(),
                ):
                    arguments[arg_key] = input_val

                invocation: InvocationResult = self.class_wrapper.invoke(
                    fun_name,
                    state,
                    Arguments(arguments),
                )

                updated_state = invocation.updated_state

                print("NEW RESULTS")
                print(invocation.return_results)
                print(updated_state.get())

                next_node_id = current_node["node"].next[0]
                event.payload["current_flow"] = next_node_id
                next_node = event.payload["flow"][str(next_node_id)]["node"]

                for key, res in zip(
                    current_node["node"].output.keys(), invocation.return_results
                ):
                    current_node["node"].output[key] = res

                # TODO, HIER NAAR KIJKEN
                for node_output in current_node["node"].output.keys():
                    if node_output in next_node.input:
                        next_node.input[node_output] = current_node["node"].output[
                            node_output
                        ]

                print(next_node.input)

            current_node["status"] = "FINISHED"

        if updated_state is not None:
            return return_event, bytes(
                self.serializer.serialize_dict(updated_state.get()), "utf-8"
            )
        return return_event, updated_state
