from src.dataflow.address import FunctionType, FunctionAddress
from typing import Dict, Any, List, Tuple, Optional, TypeVar
from src.dataflow.state import State
from src.dataflow.args import Arguments
from src.wrappers.class_wrapper import ClassWrapper, InvocationResult, FailedInvocation
from dataclasses import dataclass

"""
A definition of Null next to None.

It is necessary for finding the correct input variables for a EventFlowNode.
In some situations None is an actual parameter, this will be problematic if we initialize also using None.
Our framework will think we did not find the argument yet (and will search in the graph), whereas it is already set.
"""
Null = "__Null__"


@dataclass
class InvokeMethodRequest:
    """Wrapper class to indicate that we need to invoke an (external) method. This is returned by a method
    which is split. It holds all the information necessary for an invocation.
    """

    class_name: str
    instance_ref_var: "InternalClassRef"
    method_to_invoke: str
    args: List[Any]


class InternalClassRef:
    """Internal representation of another class."""

    def __init__(self, key: str, fun_type: FunctionType, attributes: Dict[str, Any]):
        """Initializes an internal class reference.

        This is passed as parameter to a stateful function.

        :param key: the key of the instance.
        :param fun_type: the type of the function.
        :param attributes: all attributes of this function.
        """
        self._key: str = key
        self._fun_type: FunctionType = fun_type
        self.__attributes: Dict[str, Any] = attributes

        for n, attr in attributes.items():
            setattr(self, n, attr)

    def __key(self) -> str:
        return self._key

    def __to_dict(self) -> Dict:
        return {"key": self._key, "fun_type": self._fun_type.to_dict()}


class EventFlowNode:

    REQUEST_STATE = "REQUEST_STATE"
    INVOKE_SPLIT_FUN = "INVOKE_SPLIT_FUN"

    INVOKE_EXTERNAL = "INVOKE_EXTERNAL"

    RETURN = "RETURN"
    START = "START"

    def __init__(self, typ: str, fun_type: FunctionType, id: int):
        self.id = id
        self.typ = typ
        self.fun_type = fun_type

        self.input = {}
        self.output = {}

        self.status = "PENDING"

        self.next: List[int] = []
        self.previous: int = -1

    def set_previous(self, previous: int):
        self.previous = previous

    def set_next(self, next: List[int]):
        """Set the next EventFlowNode.
        If there already exist a self.next, the input is extended.

        :param next: the next node(s).
        """
        if isinstance(next, list):
            self.next.extend(next)
        else:
            self.next.extend([next])

    def step(
        self, event_flow: "EventFlowGraph", state: State
    ) -> Tuple["EventFlowNode", State]:
        raise NotImplementedError("This should be implemented by each of the nodes.")

    def get_next(self) -> List[int]:
        return self.next

    def to_dict(self) -> Dict:
        if self.fun_type:
            fun_type_dict = self.fun_type.to_dict()
        else:
            fun_type_dict = None

        return {
            "type": self.typ,
            "fun_type": fun_type_dict,
            "id": self.id,
            "input": self.input,
            "output": self.output,
            "next": self.next,
            "previous": self.previous,
        }

    @staticmethod
    def from_dict(dict: Dict) -> "EventFlowNode":
        if dict["fun_type"] is not None:
            fun_type = FunctionType(
                dict["fun_type"]["namespace"],
                dict["fun_type"]["name"],
                dict["fun_type"]["stateful"],
            )
        else:
            fun_type = None

        flow_type = dict["type"]
        new_node = None
        if flow_type == EventFlowNode.START:
            new_node = StartNode.construct(fun_type, dict)
        elif flow_type == EventFlowNode.RETURN:
            new_node = ReturnNode.construct(fun_type, dict)
        elif flow_type == EventFlowNode.INVOKE_SPLIT_FUN:
            new_node = InvokeSplitFun.construct(fun_type, dict)
        elif flow_type == EventFlowNode.REQUEST_STATE:
            new_node = RequestState.construct(fun_type, dict)
        elif flow_type == EventFlowNode.INVOKE_EXTERNAL:
            new_node = InvokeExternal.construct(fun_type, dict)
        else:
            raise AttributeError(f"Unknown EventFlowNode type {flow_type}.")

        new_node.input = dict["input"]
        new_node.output = dict["output"]
        new_node.next = dict["next"]
        new_node.previous = dict["previous"]

        return new_node


class EventFlowGraph:
    __slots__ = "current_node", "graph", "id_to_node"

    def __init__(self, current_node: EventFlowNode, graph: List[EventFlowNode]):
        self.current_node: EventFlowNode = current_node
        self.graph: EventFlowGraph = graph

        self.id_to_node: Dict[str, EventFlowNode] = {
            str(node.id): node for node in graph
        }

    def step(self, class_wrapper: ClassWrapper = None, state: State = None) -> State:
        next_node, updated_state = self.current_node.step(self, class_wrapper, state)
        self.current_node.status = "FINISHED"
        self.current_node = next_node

        return updated_state

    def get_current(self) -> EventFlowNode:
        return self.current_node

    def get_node_by_id(self, id) -> Optional[EventFlowNode]:
        return self.id_to_node.get(str(id))

    def to_dict(self):
        return_dict = {}
        return_dict["current"] = self.current_node.id

        for node in self.graph:
            return_dict[node.id] = node.to_dict()

        return return_dict

    @staticmethod
    def from_dict(input_dict: Dict):
        current_id: str = input_dict.pop("current")

        current_node: EventFlowNode = None
        all_nodes: List[EventFlowNode] = []

        for node_id, node in input_dict.items():
            node_parsed: EventFlowNode = EventFlowNode.from_dict(node)
            all_nodes.append(node_parsed)

            if str(node_id) == str(current_id):
                current_node = node_parsed

        if not current_node:
            raise AttributeError(
                f"Couldn't find current node with id {current_id}, with keys {input_dict.keys()}"
            )

        return EventFlowGraph(current_node, all_nodes)


class StartNode(EventFlowNode):
    def __init__(self, id: int):
        super().__init__(EventFlowNode.START, None, id)

        # There is no previous.
        self.previous = -1

    def to_dict(self):
        return super().to_dict()

    def step(
        self, graph: EventFlowGraph, class_wrapper: ClassWrapper, state: State
    ) -> Tuple[EventFlowNode, State]:
        # We assume the start node has only one next node.
        return graph.get_node_by_id(self.next[0]), state

    @staticmethod
    def construct(fun_type: FunctionType, dict: Dict) -> EventFlowNode:
        return StartNode(dict["id"])


class ReturnNode(EventFlowNode):
    def __init__(self, id: int):
        super().__init__(EventFlowNode.RETURN, None, id)

    def to_dict(self):
        return super().to_dict()

    def step(
        self, graph: EventFlowGraph, class_wrapper: ClassWrapper, state: State
    ) -> Tuple[EventFlowNode, State]:
        return self, state

    def get_results(self):
        return self.output["results"]

    def set_results(self, return_results):
        self.output["results"] = return_results

    @staticmethod
    def construct(fun_type: FunctionType, dict: Dict) -> EventFlowNode:
        return ReturnNode(dict["id"])


class InvokeExternal(EventFlowNode):
    def __init__(
        self, fun_type, id, ref_variable_name, method_name, args: List[str], key=None
    ):
        super().__init__(EventFlowNode.INVOKE_EXTERNAL, fun_type, id)
        self.ref_variable_name = ref_variable_name
        self.fun_name = method_name
        self.args = args
        self.key = key

        for arg in args:
            self.input[arg] = Null

        self.output[f"{self.fun_name}_return"] = Null

    def _set_return_result(self, output: Any):
        self.output[f"{self.fun_name}_return"] = output

    def step(
        self, graph: EventFlowGraph, class_wrapper: ClassWrapper, state: State
    ) -> Tuple[EventFlowNode, State]:
        # Prepare arguments for this invocation.
        args: Arguments = Arguments(self.input)

        # Invoke the method.
        invocation: InvocationResult = self.class_wrapper.invoke(
            self.fun_name,
            state,
            Arguments(args),
        )

        """ Two scenarios:
        1. TODO Invocation has failed, we need to handle this somehow.
        2. Invocation is successful and we go to the next node. We assume the next node is always a InvokeSplitFun.
        """

        # We assume there is always only one node this EventFlowNode type.
        next_node: InvokeSplitFun = self.next[0]
        self._set_return_result(invocation.return_results)

        return next_node, invocation.updated_state

    def set_key(self, key: str):
        self.key = key

    def to_dict(self) -> Dict:
        return_dict = super().to_dict()
        return_dict["ref_variable_name"] = self.ref_variable_name
        return_dict["fun_name"] = self.fun_name
        return_dict["args"] = self.args
        return_dict["key"] = self.key

        return return_dict

    @staticmethod
    def construct(fun_type: FunctionType, dict: Dict):
        if "key" in dict:
            key = dict["key"]
        else:
            key = None
        return InvokeExternal(
            fun_type,
            dict["id"],
            dict["ref_variable_name"],
            dict["fun_name"],
            dict["args"],
            key,
        )


class InvokeSplitFun(EventFlowNode):
    def __init__(
        self,
        fun_type: FunctionType,
        id: int,
        fun_name: str,
        params: List[str],
        definitions: List[str],
        typed_params: List[str],
    ):
        super().__init__(EventFlowNode.INVOKE_SPLIT_FUN, fun_type, id)
        self.fun_name: str = fun_name
        self.params = params
        self.definitions = definitions
        self.typed_params = typed_params

        for param in params:
            self.input[param] = Null

        for definition in self.definitions:
            self.output[definition] = Null

    def _collect_incomplete_input(
        self, graph: EventFlowGraph, input_variables: List[str]
    ) -> Dict[str, Any]:
        """Collects incomplete input variables of this node by traversing the graph.

        :param graph: the graph to traverse.
        :param input_variables: the input variables that we still have to find.
        :return: a mapping from the input variable to its value.
        """
        previous = graph.get_node_by_id(self.previous)
        output: Dict[str, Any] = {}

        while len(input_variables) > 0 and previous is not None:
            for key in previous.output.keys():
                if key in input_variables:
                    """We cover two cases here:
                    1. Previous node is a REQUEST_STATE one. We create an InternalClassRef and set that input variable.
                    2. It is any other node, now if the variable name is _in_ the output of this node
                        then we set this as input for this node.
                    TODO: Consider just passing a InternalClassRef around.
                    """
                    if previous.typ == EventFlowNode.REQUEST_STATE:
                        request_state_output: Dict[str, Any] = previous.output[key]
                        key_of_state: str = request_state_output.pop("__key")

                        internal_class_ref = InternalClassRef(
                            key_of_state, previous.fun_type, request_state_output
                        )

                        output[key] = internal_class_ref
                    else:
                        output[key] = previous.output[key]

                    # We found the variable, so we don't need to look for it anymore.
                    input_variables.remove(key)

            # We do a step backwards in the state machine.
            previous = graph.get_node_by_id(previous.previous)

        if len(input_variables) > 0:
            raise AttributeError(
                f"We can't find all input variables for this (splitted) function in the flow graph: {self.fun_name}. Missing inputs: {input_variables}"
            )

        return output

    def _get_next_node_by_type(
        self, graph: EventFlowGraph, node_type: str
    ) -> EventFlowNode:
        """Returns the next node by a certain type.
        Assumes there is only one next node _per_ type.

        :param graph: the graph to obtain the actual nodes.
        :param node_type: the type to look for.
        :return: the corresponding EventFlowNode.
        """
        return [
            graph.get_node_by_id(i)
            for i in self.next
            if graph.get_node_by_id(i).typ == node_type
        ][0]

    def step(
        self, graph: EventFlowGraph, class_wrapper: ClassWrapper, state: State
    ) -> Tuple[EventFlowNode, State]:
        # TODO We need to check if the input needs to be transformed to InternalClassRef
        # Maybe add typed param list?
        # DEBUG ARGUMENTS
        incomplete_input: List[str] = [
            key for key in self.input.keys() if key == Null or key in self.typed_params
        ]

        # Constructs the function arguments.
        # We _copy_ the self.input rather than overriding, this prevents us in sending duplicate
        # information in the event (i.e. it is already stored in output of previous nodes).
        fun_arguments = Arguments(
            {
                **self.input,
                **self._collect_incomplete_input(graph, incomplete_input),
            }
        )

        # Invocation of the actual 'splitted' method.
        invocation: InvocationResult = class_wrapper.invoke(
            self.fun_name, state, fun_arguments
        )

        """ Based on the invocation we consider three scenarios:
        1. Invocation failed, we need somehow to go back to the client and throw an error (TODO: not implemented).
        2. Invocation successful, and this is a splitting point towards another function.
            In this scenario, we traverse towards the return node.
        3. Invocation successful, but we stumbled upon a return which has been defined by the programmer.
            In this scenario, we traverse towards the return node.
        """

        # Step 1, a failed invocation. TODO: needs proper handling.
        if isinstance(invocation, FailedInvocation):
            raise AttributeError(
                f"Expected a successful invocation but got a failed one: {invocation.message}."
            )

        return_results: List = invocation.results_as_list()

        # Step 2, we come across an InvokeMethodRequest and need to go the InvokeExternal node.
        next_node: EventFlowNode
        if not any(isinstance(item, InvokeMethodRequest) for item in return_results):
            # Set the output of this node. We assume a correct order.
            # I.e. the definitions names correspond to the output order.
            print(
                f"Definitions of {self.fun_name}: {self.definitions}. \nResults: {return_results}"
            )
            assert len(self.definitions) == (len(return_results) - 1)
            for i, decl in enumerate(self.definitions):
                if isinstance(
                    return_results[i], InternalClassRef
                ):  # We treat an InternalClassRef a bit differently.
                    self.output[decl] = return_results[i].to_dict()
                else:
                    self.output[decl] = return_results[i]

            # Get the InvocationRequest of this node.
            invoke_method_request: InvokeMethodRequest = return_results[-1]

            # Get the next node.
            next_node: InvokeExternal = self._get_next_node_by_type(
                graph, EventFlowNode.INVOKE_EXTERNAL
            )

            # Prepare next node by setting the address key and the arguments.
            next_node.set_key(invoke_method_request.instance_ref_var.__key())

            # We assume that arguments in the InvokeMethodRequest are in the correct order.
            for i, arg_key in enumerate(next_node.input.keys()):
                next_node.input[arg_key] = invoke_method_request.args[i]

        else:  # Step 3, we need to go the ReturnNode.
            next_node: ReturnNode = self._get_next_node_by_type(
                graph, EventFlowNode.RETURN
            )

            next_node.set_results(invocation.results_as_list())

        return next_node, invocation.updated_state

    def to_dict(self) -> Dict:
        return_dict = super().to_dict()
        return_dict["fun_name"] = self.fun_name
        return_dict["params"] = self.params
        return_dict["typed_params"] = self.typed_params
        return_dict["definitions"] = self.definitions

        return return_dict

    @staticmethod
    def construct(fun_type: FunctionType, dict: Dict):
        return InvokeSplitFun(
            fun_type,
            dict["id"],
            dict["fun_name"],
            dict["params"],
            dict["definitions"],
            dict["typed_params"],
        )


class RequestState(EventFlowNode):
    """A RequestState node is used to get the complete state from a given stateful function.

    It is expected that the client sets the request key. This is the key of the FunctionType to find the correct
    instance (effectively this is a FunctionAddress).

    Finally, in the step function the `var_name` is set with the correct state.
    This result is later used for subsequent nodes.
    """

    def __init__(self, fun_type: FunctionType, id: int, var_name: str):
        super().__init__(EventFlowNode.REQUEST_STATE, fun_type, id)
        self.var_name: str = var_name

        # Inputs for this node.
        self.input["__key"] = None

        # Outputs for this node.
        self.output[self.var_name] = None

    def set_request_key(self, key: str):
        self.input["__key"] = key

    def get_request_key(self) -> str:
        return self.input["__key"]

    def set_state_result(self, state: Dict):
        self.output[self.var_name] = state

    def step(
        self, graph: EventFlowGraph, class_wrapper: ClassWrapper, state: State
    ) -> Tuple[EventFlowNode, State]:
        state_get = state.get()

        # We copy the key, so that subsequent nodes can use it.
        state_get["__key"] = self.input["__key"]
        self.set_state_result(state_get)

        # We kind of assume that for GetState, it is is 'sequential' flow. So there is only 1 node next.
        next_node = graph.get_node_by_id(self.next[0])

        return next_node, state

    def to_dict(self) -> Dict:
        return_dict = super().to_dict()
        return_dict["var_name"] = self.var_name
        return return_dict

    @staticmethod
    def construct(fun_type: FunctionType, dict: Dict):
        return RequestState(fun_type, dict["id"], dict["var_name"])
