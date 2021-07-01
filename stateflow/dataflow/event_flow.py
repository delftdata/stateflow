from stateflow.dataflow.address import FunctionAddress
from typing import Dict, Any, List, Tuple, Optional
from stateflow.dataflow.state import State
from stateflow.dataflow.args import Arguments
from stateflow.wrappers.class_wrapper import (
    ClassWrapper,
    InvocationResult,
    FailedInvocation,
)
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

    def __init__(self, fun_addr: FunctionAddress, attributes: Dict[str, Any] = {}):
        """Initializes an internal class reference.

        This is passed as parameter to a stateful function.

        :param key: the key of the instance.
        :param fun_type: the type of the function.
        :param attributes: all attributes of this function.
        """
        self._fun_addr: FunctionAddress = fun_addr
        self._attributes: Dict[str, Any] = attributes

        for n, attr in attributes.items():
            setattr(self, n, attr)

    def _get_key(self) -> str:
        return self._fun_addr.key

    def _to_dict(self) -> Dict:
        return {
            "fun_addr": self._fun_addr.to_dict(),
            "_type": "InternalClassRef",
        }


class EventFlowNode:

    REQUEST_STATE = "REQUEST_STATE"
    INVOKE_SPLIT_FUN = "INVOKE_SPLIT_FUN"

    INVOKE_CONDITIONAL = "INVOKE_CONDITIONAL"
    INVOKE_FOR = "INVOKE_FOR"

    INVOKE_EXTERNAL = "INVOKE_EXTERNAL"

    RETURN = "RETURN"
    START = "START"

    def __init__(
        self, typ: str, fun_addr: FunctionAddress, id: int, method_id: int = 0
    ):
        self.id = id
        self.typ = typ
        self.fun_addr = fun_addr
        self.method_id = method_id

        self.input = {}
        self.output = {}

        self.status = "PENDING"

        self.next: List[int] = []
        self.previous: int = -1

    def set_previous(self, previous: int):
        self.previous = previous

    def resolve_next(self, nodes: List["EventFlowNode"], block):
        self.set_next(nodes[0].id)

    def set_next(self, next: List[int]):
        """Set the next EventFlowNode.
        If there already exist a self.next, the input is extended.

        :param next: the next node(s).
        """
        if isinstance(next, list):
            self.next.extend(next)
        else:
            self.next.extend([next])

    def _to_class_ref(self, value: Dict[str, Any]) -> InternalClassRef:
        fun_addr = FunctionAddress.from_dict(value["fun_addr"])
        return InternalClassRef(fun_addr)

    def _insert_internal_class_refs(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # TODO If we switch to a different serializer, this is not necessary...
        for arg_key, value in args.copy().items():
            if isinstance(value, dict) and value.get("_type") == "InternalClassRef":
                args[arg_key] = self._to_class_ref(value)
            elif isinstance(value, list) and all(
                isinstance(el, dict) and el.get("_type") == "InternalClassRef"
                for el in value
            ):
                # print(
                #     f"here transform to class refs {[self._to_class_ref(el) for el in value]}"
                # )
                args[arg_key] = [self._to_class_ref(el) for el in value]

        return args

    def _collect_incomplete_input(
        self, graph: "EventFlowGraph", input_variables: List[str]
    ) -> Dict[str, Any]:
        """Collects incomplete input variables of this node by traversing the graph.

        :param graph: the graph to traverse.
        :param input_variables: the input variables that we still have to find.
        :return: a mapping from the input variable to its value.
        """
        previous = graph.get_node_by_id(self.previous)
        output: Dict[str, Any] = {}

        while len(input_variables) > 0 and previous is not None:
            # We skip scopes of other method calls.
            # print(
            #     f"Now looking in {previous.typ} with {previous.id} and method {previous.method_id}"
            # )
            if previous.method_id == self.method_id:
                for key in previous.output.keys():
                    if key in input_variables:
                        """We cover two cases here:
                        1. Previous node is a REQUEST_STATE one. We create an InternalClassRef and set that input variable.
                        2. It is any other node, now if the variable name is _in_ the output of this node
                            then we set this as input for this node.
                        TODO: Consider just passing a InternalClassRef around.
                        """
                        # if previous.typ == EventFlowNode.REQUEST_STATE:
                        #     request_state_output: Dict[str, Any] = previous.output[key]
                        #     print(request_state_output)
                        #     key_of_state: str = request_state_output.get("__key")
                        #
                        #     internal_class_ref = InternalClassRef(
                        #         key_of_state, previous.fun_type, request_state_output
                        #     )
                        #
                        #     output[key] = internal_class_ref
                        if previous.output[key] is not Null:
                            output[key] = previous.output[key]

                        # We found the variable, so we don't need to look for it anymore.
                        input_variables.remove(key)

            # We do a step backwards in the state machine.
            if isinstance(previous, InvokeFor):
                previous = graph.get_node_by_id(previous.before_for_node)
            else:
                previous = graph.get_node_by_id(previous.previous)

        if len(input_variables) > 0:
            raise AttributeError(
                f"We can't find all input variables for this (splitted) function in the flow graph: {self.fun_name}. Missing inputs: {input_variables}"
            )

        return output

    def step(
        self, event_flow: "EventFlowGraph", state: State, instance: Any = None
    ) -> Tuple["EventFlowNode", State, Any]:
        raise NotImplementedError("This should be implemented by each of the nodes.")

    def get_next(self) -> List[int]:
        return self.next

    def to_dict(self) -> Dict:
        if self.fun_addr:
            fun_addr_dict = self.fun_addr.to_dict()
        else:
            fun_addr_dict = None

        return {
            "type": self.typ,
            "fun_addr": fun_addr_dict,
            "id": self.id,
            "input": self.input,
            "output": self.output,
            "next": self.next,
            "previous": self.previous,
        }

    @staticmethod
    def from_dict(dict: Dict) -> "EventFlowNode":
        if dict["fun_addr"] is not None:
            fun_addr = FunctionAddress.from_dict(dict["fun_addr"])
        else:
            fun_addr = None

        flow_type = dict["type"]
        new_node = None
        if flow_type == EventFlowNode.START:
            new_node = StartNode.construct(fun_addr, dict)
        elif flow_type == EventFlowNode.RETURN:
            new_node = ReturnNode.construct(fun_addr, dict)
        elif flow_type == EventFlowNode.INVOKE_SPLIT_FUN:
            new_node = InvokeSplitFun.construct(fun_addr, dict)
        elif flow_type == EventFlowNode.REQUEST_STATE:
            new_node = RequestState.construct(fun_addr, dict)
        elif flow_type == EventFlowNode.INVOKE_EXTERNAL:
            new_node = InvokeExternal.construct(fun_addr, dict)
        elif flow_type == EventFlowNode.INVOKE_CONDITIONAL:
            new_node = InvokeConditional.construct(fun_addr, dict)
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

    def step(
        self,
        class_wrapper: ClassWrapper = None,
        state: State = None,
        instance: Any = None,
    ) -> Tuple[State, Any]:
        next_node, updated_state, instance = self.current_node.step(
            self, class_wrapper, state, instance
        )
        self.current_node.status = "FINISHED"

        # Dynamic update of the previous node.
        next_node.previous = self.current_node.id
        self.current_node = next_node

        return updated_state, instance

    def set_function_address(
        self, current_node: EventFlowNode, method_id: int, address: FunctionAddress
    ):
        stack: List[EventFlowNode] = [current_node]
        discovered: List[int] = []

        while len(stack) > 0:
            current: EventFlowNode = stack.pop()

            if current.id in discovered:
                continue

            discovered.append(current.id)

            if (
                current.method_id == method_id
                and not isinstance(current, RequestState)
                and not isinstance(current, InvokeExternal)
            ):
                assert current.fun_addr.function_type == address.function_type
                current.fun_addr = address

            for n in current.next:
                stack.append(self.get_node_by_id(n))

    def get_current(self) -> EventFlowNode:
        return self.current_node

    def get_node_by_id(self, id) -> Optional[EventFlowNode]:
        return self.id_to_node.get(str(id))

    @staticmethod
    def construct_and_assign_arguments(
        flow: List[EventFlowNode], fun_addr: FunctionAddress, args: Arguments
    ) -> "EventFlowGraph":
        to_assign: List[str] = list(args.get_keys())
        flow_for_params: List[EventFlowNode] = []

        # Get the first nodes up and until the first InvokeSplitFun.
        # For example: RequestState, RequestState, InvokeSplitFun.
        for f in flow:
            flow_for_params.append(f)
            if f.typ == EventFlowNode.INVOKE_SPLIT_FUN:
                break

        for f in flow_for_params:
            to_remove = []
            for arg in to_assign:
                arg_value = args[arg]

                if f.typ == EventFlowNode.REQUEST_STATE and f.var_name == arg:
                    f.set_request_key(arg_value._get_key())
                    f.fun_addr.key = arg_value._get_key()
                    to_remove.append(arg)
                elif arg in f.input:
                    f.input[arg] = arg_value
                    to_remove.append(arg)
            to_assign = [el for el in to_assign if el not in to_remove]

        flow_graph = EventFlowGraph(flow[0], flow)
        flow_graph.set_function_address(flow[0], 0, fun_addr)
        flow_graph.step()

        return flow_graph

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
    def __init__(self, id: int, fun_addr: FunctionAddress, key: str = ""):
        super().__init__(EventFlowNode.START, fun_addr, id)

        self.key: str = key

        # There is no previous.
        self.previous = -1

    def to_dict(self):
        return_dict = super().to_dict()
        return_dict["key"] = self.key

        return return_dict

    def step(
        self,
        graph: EventFlowGraph,
        class_wrapper: ClassWrapper,
        state: State,
        instance: Any = None,
    ) -> Tuple[EventFlowNode, State, Any]:
        # We assume the start node has only one next node.
        return graph.get_node_by_id(self.next[0]), state, instance

    @staticmethod
    def construct(fun_addr: FunctionAddress, dict: Dict) -> EventFlowNode:
        return StartNode(dict["id"], fun_addr, dict["key"])


class ReturnNode(EventFlowNode):
    def __init__(self, id: int, fun_addr: FunctionAddress, return_name: str = ""):
        super().__init__(EventFlowNode.RETURN, fun_addr, id)
        self.return_name = return_name

    def to_dict(self):
        return_dict = super().to_dict()
        return_dict["return_name"] = self.return_name

        return return_dict

    def is_last(self) -> bool:
        return self.next == -1 or self.next == []

    def step(
        self,
        graph: EventFlowGraph,
        class_wrapper: ClassWrapper,
        state: State,
        instance: Any,
    ) -> Tuple[EventFlowNode, State, Any]:
        if self.next == [] or self.next == -1:
            return self, state, instance

        # TODO, We assume only 1 next node.
        next_node = graph.get_node_by_id(self.next[0])
        next_node.input[self.return_name] = self.get_results()
        return next_node, state, instance

    def get_results(self):
        return self.output["results"]

    def set_results(self, return_results):
        self.output["results"] = return_results

    @staticmethod
    def construct(fun_addr: FunctionAddress, dict: Dict) -> EventFlowNode:
        return ReturnNode(dict["id"], fun_addr, dict["return_name"])


class InvokeExternal(EventFlowNode):
    def __init__(
        self, fun_addr: FunctionAddress, id, method_name, args: List[str], key=None
    ):
        super().__init__(EventFlowNode.INVOKE_EXTERNAL, fun_addr, id)
        self.fun_name = method_name
        self.args = args
        self.key = key

        for arg in args:
            self.input[arg] = Null

        self.output[f"{self.fun_name}_return"] = Null

    def _set_return_result(self, output: Any):
        self.output[self.get_output_name()] = output

    def get_output_name(self) -> str:
        return f"{self.fun_name}_return"

    def step(
        self,
        graph: EventFlowGraph,
        class_wrapper: ClassWrapper,
        state: State,
        instance: Any = None,
    ) -> Tuple[EventFlowNode, State, Any]:
        # Prepare arguments for this invocation.
        args: Arguments = Arguments(self.input)

        # Invoke the method.
        # print(f"Now invoking external method {self.fun_name} with args {args.get()}")
        if not instance:
            invocation, instance = class_wrapper.invoke_return_instance(
                self.fun_name,
                state,
                args,
            )
        else:
            invocation: InvocationResult = class_wrapper.invoke_with_instance(
                self.fun_name,
                instance,
                args,
            )

        """ Two scenarios:
        1. TODO Invocation has failed, we need to handle this somehow.
        2. Invocation is successful and we go to the next node. We assume the next node is always a InvokeSplitFun or RequestState.
        """

        # We assume there is always only one next node for this EventFlowNode type.
        next_node: EventFlowNode = graph.get_node_by_id(self.next[0])
        if isinstance(next_node, InvokeSplitFun) or isinstance(
            next_node, InvokeConditional
        ):
            self._set_return_result(invocation.return_results)
        elif isinstance(next_node, RequestState):
            instance_var = self._collect_incomplete_input(graph, [next_node.var_name])[
                next_node.var_name
            ]
            next_node.set_request_key(instance_var._get_key())
            next_node.fun_addr.key = instance_var._get_key()
        else:
            raise AttributeError(f"Unknown next node {next_node}.")

        return next_node, invocation.updated_state, instance

    def __eq__(self, other):
        if not isinstance(other, InvokeExternal):
            return False
        else:
            return self.to_dict() == other.to_dict()

    def set_key(self, key: str):
        self.key = key

    def to_dict(self) -> Dict:
        return_dict = super().to_dict()
        return_dict["fun_name"] = self.fun_name
        return_dict["args"] = self.args
        return_dict["key"] = self.key

        return return_dict

    @staticmethod
    def construct(fun_addr: FunctionAddress, dict: Dict):
        if "key" in dict:
            key = dict["key"]
        else:
            key = None
        return InvokeExternal(
            fun_addr,
            dict["id"],
            dict["fun_name"],
            dict["args"],
            key,
        )


class InvokeSplitFun(EventFlowNode):
    def __init__(
        self,
        fun_addr: FunctionAddress,
        id: int,
        fun_name: str,
        params: List[str],
        definitions: List[str],
        typed_params: List[str],
    ):
        super().__init__(EventFlowNode.INVOKE_SPLIT_FUN, fun_addr, id)
        self.fun_name: str = fun_name
        self.params = params
        self.definitions = definitions
        self.typed_params = typed_params

        for param in params:
            self.input[param] = Null

        for definition in self.definitions:
            self.output[definition] = Null

    def _get_next_node_by_type(
        self, graph: EventFlowGraph, node_type: str
    ) -> Optional[EventFlowNode]:
        """Returns the next node by a certain type.
        Assumes there is only one next node _per_ type.

        :param graph: the graph to obtain the actual nodes.
        :param node_type: the type to look for.
        :return: the corresponding EventFlowNode.
        """
        nodes = [
            graph.get_node_by_id(i)
            for i in self.next
            if graph.get_node_by_id(i).typ == node_type
        ]

        if len(nodes) == 1:
            return nodes[0]
        elif len(nodes) == 0:
            return None

        raise AttributeError(f"Did not expect next nodes of the same type {nodes}.")

    def _get_next_node_by_not_type(
        self, graph: EventFlowGraph, node_type: str
    ) -> EventFlowNode:
        """Returns the next node which is not equal to a certain type.
        Assumes there is only 2 next nodes.

        :param graph: the graph to obtain the actual nodes.
        :param node_type: the type to not look for.
        :return: the corresponding EventFlowNode.
        """
        return [
            graph.get_node_by_id(i)
            for i in self.next
            if graph.get_node_by_id(i).typ != node_type
        ][0]

    def _set_definitions(self, return_results: List):
        for i, decl in enumerate(self.definitions):
            if isinstance(
                return_results[i], InternalClassRef
            ):  # We treat an InternalClassRef a bit differently.
                self.output[decl] = return_results[i]
            elif isinstance(return_results[i], list) and all(
                isinstance(el, InternalClassRef) for el in return_results[i]
            ):
                self.output[decl] = [el._to_dict() for el in return_results[i]]
            else:
                # print(f"Now setting {decl} to {return_results[i]}")
                self.output[decl] = return_results[i]

    def step(
        self,
        graph: EventFlowGraph,
        class_wrapper: ClassWrapper,
        state: State,
        instance: Any = None,
    ) -> Tuple[EventFlowNode, State, Any]:
        # TODO We need to check if the input needs to be transformed to InternalClassRef
        incomplete_input: List[str] = [
            key for key in self.input.keys() if self.input[key] == Null
        ]

        # print(
        #     f"Now trying to invoke method {self.fun_name}. The input we still have to search: {incomplete_input}. All input variables are: {list(self.input.keys())}"
        # )

        # Constructs the function arguments.
        # We _copy_ the self.input rather than overriding, this prevents us in sending duplicate
        # information in the event (i.e. it is already stored in output of previous nodes).
        all_input = self._insert_internal_class_refs(
            {
                **self.input,
                **self._collect_incomplete_input(graph, incomplete_input),
            }
        )

        # print(f"All input: {all_input}")

        fun_arguments = Arguments(all_input)

        # Invocation of the actual 'splitted' method.
        if not instance:
            invocation, instance = class_wrapper.invoke_return_instance(
                self.fun_name,
                state,
                fun_arguments,
            )
        else:
            invocation: InvocationResult = class_wrapper.invoke_with_instance(
                self.fun_name,
                instance,
                fun_arguments,
            )
        """ Based on the invocation we consider three scenarios:
        1. Invocation failed, we need somehow to go back to the client and throw an error (TODO: not implemented).
        2. Invocation successful, and this is a splitting point towards another function.
            In this scenario, we traverse towards the return node.
        3. Invocation successful, but we stumbled upon a return which has been defined by the programmer.
            In this scenario, we traverse towards the return node.
        """

        # Step 1, a failed invocation. TODO: needs proper self._get_output_name()handling.
        if isinstance(invocation, FailedInvocation):
            raise AttributeError(
                f"Expected a successful invocation but got a failed one: {invocation.message}."
            )

        return_results: List = invocation.results_as_list()

        # Step 2, we come across an InvokeMethodRequest and need to go the InvokeExternal node.
        next_node: EventFlowNode
        if (
            len(return_results) > 0
            and isinstance(return_results[-1], dict)
            and return_results[-1].get("_type") == "InvokeMethodRequest"
        ):
            # Set the output of this node. We assume a correct order.
            # I.e. the definitions names correspond to the output order.
            # A mapping from a class instance variable, to its key.
            self._set_definitions(return_results)

            # Get the InvocationRequest of this node.
            invoke_method_request: Dict = return_results[-1]

            # Get the next node.
            next_node: InvokeExternal = self._get_next_node_by_type(
                graph, EventFlowNode.INVOKE_EXTERNAL
            )

            if next_node:
                next_node.set_key(invoke_method_request["call_instance_ref"])
                next_node.fun_addr.key = invoke_method_request["call_instance_ref"]

                # We assume that arguments in the InvokeMethodRequest are in the correct order.
                # print(f"Next node {next_node.id} {next_node.fun_name} { next_node}")
                # print(f"Next node keys {next_node.input.keys()}")
                for i, arg_key in enumerate(next_node.input.keys()):
                    next_node.input[arg_key] = invoke_method_request["args"][i]
            else:
                # Next node is StartNode
                next_node: StartNode = self._get_next_node_by_type(
                    graph, EventFlowNode.START
                )

                next_node.key = invoke_method_request["call_instance_ref"]
                next_node.fun_addr.key = invoke_method_request["call_instance_ref"]
                graph.set_function_address(
                    next_node, next_node.method_id, next_node.fun_addr
                )

                # TODO FIND FIX IF FIRST NODE IS REQUEST STATE!
                # print(f"Next start node keys {next_node.input.keys()}")
                # print(f"My args {invoke_method_request['args']}")
                for i, arg_key in enumerate(next_node.output.keys()):
                    next_node.output[arg_key] = invoke_method_request["args"][i]

        elif (
            len(return_results) > 0
            and isinstance(return_results[-1], dict)
            and return_results[-1].get("_type") == "NormalSplit"
        ):
            self._set_definitions(return_results)

            if self._get_next_node_by_type(graph, EventFlowNode.REQUEST_STATE):
                next_node: RequestState = self._get_next_node_by_type(
                    graph, EventFlowNode.REQUEST_STATE
                )
                if next_node.var_name in self.output:
                    next_node.set_request_key(
                        self.output[next_node.var_name]._get_key()
                    )
                    next_node.fun_addr.key = self.output[next_node.var_name]._get_key()
                else:
                    instance_var = self._collect_incomplete_input(
                        graph, [next_node.var_name]
                    )[next_node.var_name]
                    next_node.set_request_key(instance_var._get_key())
            else:
                next_node: EventFlowNode = self._get_next_node_by_not_type(
                    graph, EventFlowNode.RETURN
                )

        elif (
            len(return_results) > 0
            and isinstance(return_results[-1], dict)
            and (
                return_results[-1].get("_type") == "Continue"
                or return_results[-1].get("_type") == "Break"
            )
        ):
            self.output["_type"] = return_results[-1].get("_type")
            next_node: EventFlowNode = self._get_next_node_by_type(
                graph, EventFlowNode.INVOKE_FOR
            )
        elif (
            len(return_results) > 0
            and isinstance(return_results[-1], dict)
            and (return_results[-1].get("_type") == "ForLoopSplit")
        ):
            self._set_definitions(return_results)

            next_node: EventFlowNode = self._get_next_node_by_type(
                graph, EventFlowNode.INVOKE_FOR
            )
        else:  # Step 3, we need to go the ReturnNode.
            next_node: ReturnNode = self._get_next_node_by_type(
                graph, EventFlowNode.RETURN
            )

            if next_node.is_last():
                next_node.set_results(invocation.results_as_list())
            else:
                next_node.set_results(invocation.return_results)

        return next_node, invocation.updated_state, instance

    def to_dict(self) -> Dict:
        return_dict = super().to_dict()
        return_dict["fun_name"] = self.fun_name
        return_dict["params"] = self.params
        return_dict["typed_params"] = self.typed_params
        return_dict["definitions"] = self.definitions

        return return_dict

    @staticmethod
    def construct(fun_addr: FunctionAddress, dict: Dict):
        return InvokeSplitFun(
            fun_addr,
            dict["id"],
            dict["fun_name"],
            dict["params"],
            dict["definitions"],
            dict["typed_params"],
        )


class InvokeConditional(EventFlowNode):
    def __init__(
        self,
        fun_addr: FunctionAddress,
        id: int,
        fun_name: str,
        params: List[str],
        if_true_node: int = -1,
        if_false_node: int = -1,
        if_true_block_id: int = -1,
        if_false_block_id: int = -1,
    ):
        super().__init__(EventFlowNode.INVOKE_CONDITIONAL, fun_addr, id)
        self.fun_name = fun_name
        self.params = params
        self.if_true_node = if_true_node
        self.if_false_node = if_false_node

        self.if_true_block_id: int = if_true_block_id
        self.if_false_block_id: int = if_false_block_id

        for param in params:
            self.input[param] = Null

        # This node has no output.

    def step(
        self,
        graph: EventFlowGraph,
        class_wrapper: ClassWrapper,
        state: State,
        instance: Any = None,
    ) -> Tuple[EventFlowNode, State, Any]:

        incomplete_input: List[str] = [
            key for key in self.input.keys() if self.input[key] == Null
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
        if not instance:
            invocation, instance = class_wrapper.invoke_return_instance(
                self.fun_name,
                state,
                fun_arguments,
            )
        else:
            invocation: InvocationResult = class_wrapper.invoke_with_instance(
                self.fun_name,
                instance,
                fun_arguments,
            )

        """ Based on the invocation we consider two scenarios:
            1. Invocation failed, we need somehow to go back to the client and throw an error (TODO: not implemented).
            2. Invocation successful, and returns True. We need to traverse the dataflow towards the 'True' block.
            3. Invocation successful, and returns False. We need to traverse the dataflow towards the 'False' block.
        """

        # Step 1, a failed invocation. TODO: needs proper handling.
        if isinstance(invocation, FailedInvocation):
            raise AttributeError(
                f"Expected a successful invocation but got a failed one: {invocation.message}."
            )

        return_results: List = invocation.results_as_list()
        cond: bool = return_results[0]

        # True path
        if cond:
            next_node = graph.get_node_by_id(self.if_true_node)
        # False path
        else:
            next_node = graph.get_node_by_id(self.if_false_node)

        if next_node.typ == EventFlowNode.REQUEST_STATE:
            if next_node.var_name in self.output:
                next_node.set_request_key(self.output[next_node.var_name]._get_key())
            else:
                instance_var = self._collect_incomplete_input(
                    graph, [next_node.var_name]
                )[next_node.var_name]
                next_node.set_request_key(instance_var._get_key())

        return next_node, invocation.updated_state, instance

    def resolve_next(self, nodes: List[EventFlowNode], block):
        next_node = nodes[0].id
        if block.block_id == self.if_true_block_id:
            self.if_true_node = next_node

        elif block.block_id == self.if_false_block_id:
            self.if_false_node = next_node
        else:
            raise AttributeError(
                "Next node for conditional is not its True nor False block."
            )

        self.set_next(next_node)

    def to_dict(self) -> Dict:
        return_dict = super().to_dict()
        return_dict["fun_name"] = self.fun_name
        return_dict["params"] = self.params
        return_dict["if_true_node"] = self.if_true_node
        return_dict["if_false_node"] = self.if_false_node

        return return_dict

    @staticmethod
    def construct(fun_addr: FunctionAddress, dict: Dict):
        return InvokeConditional(
            fun_addr,
            dict["id"],
            dict["fun_name"],
            dict["params"],
            dict["if_true_node"],
            dict["if_false_node"],
        )


class InvokeFor(EventFlowNode):
    def __init__(
        self,
        fun_addr: FunctionAddress,
        id: int,
        fun_name: str,
        iter_name: str,
        iter_target: str,
        for_body_node: int = -1,
        else_node: int = -1,
        iteration: int = 0,
        before_for_node: int = -1,
        for_body_block_id: int = -1,
        else_block_id: int = -1,
    ):

        super().__init__(EventFlowNode.INVOKE_FOR, fun_addr, id)
        self.fun_name = fun_name

        self.iter_name = iter_name
        self.iter_target = iter_target
        self.iteration: int = iteration

        self.for_body_node = for_body_node
        self.else_node = else_node

        self.for_body_block_id = for_body_block_id
        self.else_block_id = else_block_id

        self.input[iter_name] = Null
        self.output[iter_target] = Null
        self.output[iter_name] = Null

        self.before_for_node: int = before_for_node

    def _after_body_node_id(self) -> int:
        next_nodes = self.next

        for node in next_nodes:
            if node != self.for_body_node and node != self.else_node:
                return node

        return -1

    def step(
        self,
        graph: EventFlowGraph,
        class_wrapper: ClassWrapper,
        state: State,
        instance: Any = None,
    ) -> Tuple[EventFlowNode, State, Any]:

        # In this scenario we need to get the iterator from the previous block.
        if self.iteration == 0:
            iterator = graph.get_node_by_id(self.previous).output[self.iter_name]
            self.before_for_node = self.previous

        else:  # Otherwise we get it from our 'own' output.
            iterator = self.output[self.iter_name]

            # We're now going to get the output of all previous blocks until this block,
            # and set it as output for this block.
            # This is some sort of 'scope' dict, with all declared variables.
            current: EventFlowNode = graph.get_node_by_id(self.previous)
            already_found: List[str] = []
            while current.id != self.id:
                for k, v in current.output.items():
                    if k not in already_found:
                        self.output[k] = v
                        already_found.append(k)

                if isinstance(current, InvokeFor):
                    current = graph.get_node_by_id(current.before_for_node)
                elif isinstance(current, StartNode):
                    break
                else:
                    current = graph.get_node_by_id(current.previous)

        # Now we determine if we got here from a break or continue
        previous_node: EventFlowNode = graph.get_node_by_id(self.previous)
        if "_type" in previous_node.output:
            output_type = previous_node.output["_type"]

            if output_type == "Continue":
                # We don't really care...
                # print("Time to continue?!")
                pass
            elif output_type == "Break":
                # We move towards the "next" node which is not the for body
                return graph.get_node_by_id(self._after_body_node_id()), state, instance

        # Now we actually execute the iterator and put the result in the output.
        args = Arguments({self.iter_name: iterator})
        if instance:
            invoc_result = class_wrapper.invoke_with_instance(
                self.fun_name, instance, args
            )
        else:
            invoc_result, instance = class_wrapper.invoke_return_instance(
                self.fun_name, state, args
            )

        # If StopIteration is called we either go to the next node or the else node (if it exists)
        return_results = invoc_result.results_as_list()
        if (
            len(return_results) > 0
            and isinstance(return_results[-1], dict)
            and return_results[-1].get("_type") == "StopIteration"
        ):
            next_id: int = (
                self.else_node if self.else_node != -1 else self._after_body_node_id()
            )
            next_node = graph.get_node_by_id(next_id)
            self.iteration = 0
        else:
            self.iteration += 1
            # print(f"Going to the next iteration {self.iteration}")

            self.output[self.iter_target] = return_results[0]
            self.output[self.iter_name] = return_results[-1]
            next_node = graph.get_node_by_id(self.for_body_node)
            # print(f"Iteration type {next_node.typ}")

        if next_node.typ == EventFlowNode.REQUEST_STATE:
            if next_node.var_name in self.output:
                next_node.set_request_key(self.output[next_node.var_name]._get_key())
                next_node.fun_addr.key = self.output[next_node.var_name]._get_key()
            else:
                instance_var = self._collect_incomplete_input(
                    graph, [next_node.var_name]
                )[next_node.var_name]
                next_node.set_request_key(instance_var._get_key())
                next_node.fun_addr.key = instance_var._get_key()

        return next_node, state, instance

    def resolve_next(self, nodes: List[EventFlowNode], block):
        next_node = nodes[0].id
        if block.block_id == self.for_body_block_id:
            self.for_body_node = next_node
        elif block.block_id == self.else_block_id:
            self.else_node = next_node

        self.set_next(next_node)

    def to_dict(self) -> Dict:
        return_dict = super().to_dict()
        return_dict["fun_name"] = self.fun_name
        return_dict["iter_name"] = self.iter_target
        return_dict["iter_target"] = self.iter_target
        return_dict["iteration"] = self.iteration
        return_dict["before_for_node"] = self.before_for_node
        return_dict["for_body_node"] = self.for_body_node
        return_dict["else_node"] = self.else_node

        return return_dict

    @staticmethod
    def construct(fun_addr: FunctionAddress, dict: Dict):
        return InvokeFor(
            fun_addr,
            dict["id"],
            dict["fun_name"],
            dict["iter_name"],
            dict["iter_target"],
            dict["for_body_node"],
            dict["else_node"],
            dict["iteration"],
            dict["before_for_node"],
        )


class RequestState(EventFlowNode):
    """A RequestState node is used to get the complete state from a given stateful function.

    It is expected that the client sets the request key. This is the key of the FunctionType to find the correct
    instance (effectively this is a FunctionAddress).

    Finally, in the step function the `var_name` is set with the correct state.
    This result is later used for subsequent nodes.
    """

    def __init__(self, fun_addr: FunctionAddress, id: int, var_name: str):
        super().__init__(EventFlowNode.REQUEST_STATE, fun_addr, id)
        self.var_name: str = var_name

        # Inputs for this node.
        self.input["__key"] = Null

        # Outputs for this node.
        self.output[self.var_name] = Null

    def set_request_key(self, key: str):
        self.input["__key"] = key

    def get_request_key(self) -> str:
        return self.input["__key"]

    def set_state_result(self, state: Dict):
        self.output[self.var_name] = state

    def step(
        self,
        graph: EventFlowGraph,
        class_wrapper: ClassWrapper,
        state: State,
        instance=None,
    ) -> Tuple[EventFlowNode, State, Any]:
        state_get = state.get()

        # We copy the key, so that subsequent nodes can use it.
        ref = InternalClassRef(self.fun_addr, state_get)

        self.output[self.var_name] = ref

        # We kind of assume that for GetState, it is is 'sequential' flow. So there is only 1 node next.
        next_node = graph.get_node_by_id(self.next[0])

        return next_node, state, instance

    def to_dict(self) -> Dict:
        return_dict = super().to_dict()
        return_dict["var_name"] = self.var_name
        return return_dict

    @staticmethod
    def construct(fun_addr: FunctionAddress, dict: Dict):
        return RequestState(fun_addr, dict["id"], dict["var_name"])
