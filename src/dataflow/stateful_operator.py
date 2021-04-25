from src.dataflow.dataflow import Operator, Edge, FunctionType, EventType
from src.dataflow.event import Event, EventFlowNode
from src.dataflow.args import Arguments
from src.dataflow.state import State
from src.wrappers import ClassWrapper, MetaWrapper, InvocationResult, FailedInvocation
from typing import NewType, List, Tuple, Optional
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
        """Handles a request to create a new class.
        We assume that State does not yet exist for this requested class instance.

        We initialize the class with the 'args' key from the event payload.
        We return a event with the state encoded in the payload["init_class_state"].
        Moreover, we set the key of the function address.

        This event will eventually be propagated to the 'actual' stateful operator,
        where it will call `handle(event, state)` and subsequently `_handle_create_with_state(event, state)`

        :param event: the Request.InitClass event.
        :return: the created instance, embedded in an Event.
        """
        res: InvocationResult = self.class_wrapper.init_class(event.payload["args"])

        key: str = res.return_results[0]
        created_state: State = res.updated_state

        # Set the key and the state of this class.
        event.fun_address.key = key
        event.payload["init_class_state"] = created_state.get()

        # We can get rid of the arguments.
        del event.payload["args"]

        return event

    def handle(self, event: Event, state: Optional[bytes]) -> Tuple[Event, bytes]:
        if event.event_type == EventType.Request.InitClass:
            return self._handle_create_with_state(event, state)

        if state:  # If state exists, we can deserialize it.
            state = State(self.serializer.deserialize_dict(state))
        else:  # If state does not exists we can't execute these methods, so we return a KeyNotFound reply.
            return (
                event.copy(
                    event_type=EventType.Reply.KeyNotFound,
                    payload={
                        "error_message": f"Stateful instance with key={event.fun_address.key} does not exist."
                    },
                ),
                state,
            )

        updated_state = None
        return_event = None

        if event.event_type == EventType.Request.InvokeStateful:
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

                if not isinstance(invocation.return_results, list):
                    current_node["node"].output[
                        list(current_node["node"].output.keys())[0]
                    ] = invocation.return_results
                else:
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

                print(f"Current node id{current_node['node'].id}")
                print(current_node["node"].output)
                print(f"Next node id {next_node.id}")
                print(next_node.input)

                previous_node = current_node["node"]
                while None in next_node.input.values():
                    keys = [k for k, v in next_node.input.items() if v is None]
                    if previous_node.previous == -1:
                        print(f"Failed Next node id {next_node.id}")
                        print(next_node.input)
                        break
                    previous_node = event.payload["flow"][str(previous_node.previous)][
                        "node"
                    ]

                    for key, value in previous_node.output.items():
                        if key in keys:
                            next_node.input[key] = value

                print(f"Done Next node id {next_node.id}")
                print(next_node.input)

            current_node["status"] = "FINISHED"

        if updated_state is not None:
            return return_event, bytes(
                self.serializer.serialize_dict(updated_state.get()), "utf-8"
            )
        return return_event, updated_state

    def _handle_create_with_state(
        self, event: Event, state: Optional[State]
    ) -> Tuple[Event, bytes]:
        """Will 'create' this instance, by verifying if the state exists already.

        1. If state exists, we return an FailedInvocation because we can't construct the same key twice.
        2. Otherwise, we unpack the created state from the payload and return it.
            In the outgoing event, we put the key in the payload.

        :param event: the incoming InitClass event.
        :param state: the current state (in bytes), might be None.
        :return: the outgoing event and (updated) state.
        """
        if (
            state
        ):  # In this case, we already created a class before, so we will return an error.
            return (
                event.copy(
                    event_type=EventType.Reply.FailedInvocation,
                    payload={
                        "error_message": f"{event.fun_address.function_type.get_full_name()} class "
                        f"with key={event.fun_address.key} already exists."
                    },
                ),
                state,
            )

        return_event = event.copy(
            event_type=EventType.Reply.SuccessfulCreateClass,
            payload={"key": f"{event.fun_address.key}"},
        )
        new_state = event.payload["init_class_state"]
        updated_state = State(new_state)

        return return_event, bytes(
            self.serializer.serialize_dict(updated_state.get()), "utf-8"
        )
