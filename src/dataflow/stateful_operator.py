from src.dataflow.dataflow import Operator, Edge, FunctionType, EventType
from src.dataflow.event import (
    Event,
    EventFlowNode,
    FunctionType,
    EventFlowGraph,
    InternalClassRef,
)
from src.dataflow.args import Arguments
from src.dataflow.state import State
from src.wrappers import ClassWrapper, MetaWrapper, InvocationResult, FailedInvocation
from typing import NewType, List, Tuple, Optional, Dict, Any
from src.serialization.json_serde import SerDe, JsonSerializer

NoType = NewType("NoType", None)


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

    def _dispatch_event(
        self, event_type: EventType, event: Event, state: State
    ) -> Tuple[Event, State]:
        """Dispatches an event to the correct method to execute/handle it.

        :param event_type: the event_type to find the correct handle.
        :param event: the incoming event.
        :param state: the incoming state.
        :return: a tuple of outgoing event + updated state.
        """

        if event_type == EventType.Request.InvokeStateful:
            return self._handle_invoke_stateful(event, state)
        elif event_type == EventType.Request.GetState:
            return self._handle_get_state(event, state)
        elif event_type == EventType.Request.UpdateState:
            return self._handle_update_state(event, state)
        elif event_type == EventType.Request.FindClass:
            return self._handle_find_class(event, state)
        else:
            # raise AttributeError(f"Unknown event type: {event_type}.")
            return None, None

    def handle(self, event: Event, state: Optional[bytes]) -> Tuple[Event, bytes]:
        """Handles incoming event and current state.

        Depending on the event type, a method is executed or a instance is created, or state is updated, etc.

        :param event: the incoming event.
        :param state: the incoming state (in bytes). If this is None, we assume this 'key' does not exist.
        :return: a tuple of outgoing event + updated state (in bytes).
        """
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

        # We dispatch the event to find the correct execution method.
        return_event, updated_state = self._dispatch_event(
            event.event_type, event, state
        )

        if event.event_type == EventType.Request.EventFlow:
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

    def _handle_get_state(self, event: Event, state: State) -> Tuple[Event, State]:
        """Gets a field/attribute of the current state.

         The incoming event needs to have an 'attribute' field in the payload.
         We assume this attribute is available in the state and in the correct format.
         We don't check this explicitly for performance reasons.

        :param event: the incoming event.
        :param state: the current state.
        :return: a tuple of outgoing event + updated state.
        """
        return (
            event.copy(
                event_type=EventType.Reply.SuccessfulStateRequest,
                payload={"state": state[event.payload["attribute"]]},
            ),
            state,
        )

    def _handle_find_class(self, event: Event, state: State) -> Tuple[Event, State]:
        """Check if the instance of a class exists.

        If this is the case, we simply return with an empty payload and `EventType.Reply.FoundClass`.
        We assume the instance _exists_ if we get in this method. If it did not exist,
        state would have been None and we would have returned a KeyNotFound event.
        # TODO Consider renaming to FindInstance, which makes more sense from a semantic perspective.

        :param event: event: the incoming event.
        :param state: the current state.
        :return: a tuple of outgoing event + current state.
        """
        return event.copy(event_type=EventType.Reply.FoundClass, payload={}), state

    def _handle_update_state(self, event: Event, state: State) -> Tuple[Event, State]:
        """Update one attribute of the state.

        The incoming event needs to have an 'attribute' field in the payload aswell as 'attribute_value'.
        The 'attribute' field is the key of the state, whereas 'attribute_value' is the value.
        We assume this attribute is available in the state and in the correct format.
        We don't check this explicitly for performance reasons.

        :param event: the incoming event.
        :param state: the current state.
        :return: a tuple of outgoing event + updated state.
        """
        state[event.payload["attribute"]] = event.payload["attribute_value"]
        return_event = event.copy(
            event_type=EventType.Reply.SuccessfulStateRequest,
            payload={},
        )
        return return_event, state

    def _handle_invoke_stateful(
        self, event: Event, state: State
    ) -> Tuple[Event, State]:
        """Invokes a stateful method.

        The incoming event needs to have a `method_name` and `args` in its payload for the invocation.
        We assume these keys are there and in the correct format.
        We don't check this explicitly for performance reasons.

        Returns:
        1. Current state + failed event, in case the invocation failed for whatever reason.
        2. Updated state + success event, in case of successful invocation.

        :param event: the incoming event.
        :param state: the current state.
        :return: a tuple of outgoing event + updated state.
        """
        invocation: InvocationResult = self.class_wrapper.invoke(
            event.payload["method_name"], state, event.payload["args"]
        )

        if isinstance(invocation, FailedInvocation):
            return (
                event.copy(
                    event_type=EventType.Reply.FailedInvocation,
                    payload={"error_message": invocation.message},
                ),
                state,
            )
        else:
            return (
                event.copy(
                    event_type=EventType.Reply.SuccessfulInvocation,
                    payload={"return_results": invocation.return_results},
                ),
                invocation.updated_state,
            )

    def _handle_event_flow(self, event: Event, state: State) -> Tuple[Event, State]:
        flow_graph: EventFlowGraph = event.payload["flow"]
        updated_state: State = flow_graph.step(self.class_wrapper, state)

        return event, updated_state
