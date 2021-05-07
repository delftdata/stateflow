from typing import List, Optional, Dict, Tuple
from enum import Enum, EnumMeta
from src.dataflow.state import State
import ujson


class FunctionType:

    __slots__ = "namespace", "name", "stateful"

    def __init__(self, namespace: str, name: str, stateful: bool):
        self.namespace = namespace
        self.name = name
        self.stateful = stateful

    def is_stateless(self):
        return not self.stateful

    def get_full_name(self):
        return f"{self.namespace}/{self.name}"

    def __eq__(self, other):
        if not isinstance(other, FunctionType):
            return False

        namespace_eq = self.namespace == other.namespace
        name_eq = self.name == other.name
        stateful_eq = self.stateful == other.stateful

        return namespace_eq and name_eq and stateful_eq

    def to_dict(self) -> Dict:
        return {
            "namespace": self.namespace,
            "name": self.name,
            "stateful": self.stateful,
        }

    @staticmethod
    def create(desc) -> "FunctionType":
        name = desc.class_name
        namespace = "global"  # for now we have a global namespace
        stateful = True  # for now we only cover stateful functions

        return FunctionType(namespace, name, stateful)

    def __eq__(self, other):
        if not isinstance(other, FunctionType):
            return False

        return (
            self.name == other.name
            and self.namespace == other.namespace
            and self.stateful == other.stateful
        )


class FunctionAddress:
    """The address of a stateful or stateless function.

    Consists of two parts:
    - a FunctionType: the namespace and name of the function, and a flag to specify it as stateful
    - a key: an optional key, in case we deal with a stateful function.

    This address can be used to route an event correctly through a dataflow.
    """

    __slots__ = "function_type", "key"

    def __init__(self, function_type: FunctionType, key: Optional[str]):
        self.function_type = function_type
        self.key = key

    def is_stateless(self):
        return self.function_type.is_stateless()

    def to_dict(self):
        return {"function_type": self.function_type.to_dict(), "key": self.key}

    @staticmethod
    def from_dict(dictionary: Dict) -> "FunctionAddress":
        return FunctionAddress(
            FunctionType(
                dictionary["function_type"]["namespace"],
                dictionary["function_type"]["name"],
                dictionary["function_type"]["stateful"],
            ),
            dictionary["key"],
        )

    def __eq__(self, other):
        if not isinstance(other, FunctionAddress):
            return False

        return self.key == other.key and self.function_type == other.function_type


class MetaEnum(EnumMeta):
    def __contains__(cls, item):
        try:
            cls(item)
        except ValueError:
            return False
        return True


class _Request(Enum, metaclass=MetaEnum):
    InvokeStateless = "InvokeStateless"
    InvokeStateful = "InvokeStateful"
    InitClass = "InitClass"

    FindClass = "FindClass"

    GetState = "GetState"
    SetState = "SetState"
    UpdateState = "UpdateState"
    DeleteState = "DeleteState"

    EventFlow = "EventFlow"

    def __str__(self):
        return f"Request.{self.value}"


class _Reply(Enum, metaclass=MetaEnum):
    SuccessfulInvocation = "SuccessfulInvocation"
    SuccessfulCreateClass = "SuccessfulCreateClass"

    FoundClass = "FoundClass"
    KeyNotFound = "KeyNotFound"

    SuccessfulStateRequest = "SuccessfulStateRequest"
    FailedInvocation = "FailedInvocation"

    def __str__(self):
        return f"Reply.{self.value}"


class EventType:
    Request = _Request
    Reply = _Reply

    @staticmethod
    def from_str(input_str: str) -> Optional["EventType"]:
        if input_str in EventType.Request:
            return EventType.Request[input_str]
        elif input_str in EventType.Reply:
            return EventType.Reply[input_str]
        else:
            return None


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
    def __init__(self, current_node: EventFlowNode, graph: List[EventFlowNode]):
        self.current_node: EventFlowNode = current_node
        self.graph: EventFlowGraph = graph

        self.id_to_node: Dict[str, EventFlowNode] = {node.id: node for node in graph}

    def step(self, state: State) -> State:
        next_node, updated_state = self.current_node.step(self, state)
        self.current_node.status = "FINISHED"
        self.current_node = next_node

        return updated_state

    def get_current(self) -> EventFlowNode:
        return self.current_node

    def get_node_by_id(self, id):
        return self.id_to_node[str(id)]


class StartNode(EventFlowNode):
    def __init__(self, id: int):
        super().__init__(EventFlowNode.START, None, id)

    def to_dict(self):
        return super().to_dict()

    def step(self, graph: EventFlowGraph, state: State) -> Tuple[EventFlowNode, State]:
        return graph.get_node_by_id(self.next), state

    @staticmethod
    def construct(fun_type: FunctionType, dict: Dict) -> EventFlowNode:
        return StartNode(dict["id"])


class ReturnNode(EventFlowNode):
    def __init__(self, id: int):
        super().__init__(EventFlowNode.RETURN, None, id)

    def to_dict(self):
        return super().to_dict()

    def step(self, state: State):
        return self, state

    @staticmethod
    def construct(fun_type: FunctionType, dict: Dict) -> EventFlowNode:
        return ReturnNode(dict["id"])


class InvokeExternal(EventFlowNode):
    def __init__(
        self, fun_type, id, ref_variable_name, method_name, args: List[str], key=None
    ):
        super().__init__(EventFlowNode.INVOKE_EXTERNAL, fun_type, id)
        self.ref_variable_name = ref_variable_name
        self.method = method_name
        self.args = args
        self.key = key

        for arg in args:
            self.input[arg] = None

        self.output[f"{method_name}_return"] = None

    def step(self, graph: EventFlowGraph, state: State) -> Tuple[EventFlowNode, State]:
        pass

    def to_dict(self) -> Dict:
        return_dict = super().to_dict()
        return_dict["ref_variable_name"] = self.ref_variable_name
        return_dict["method"] = self.method
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
            dict["method"],
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
    ):
        super().__init__(EventFlowNode.INVOKE_SPLIT_FUN, fun_type, id)
        self.fun_name: str = fun_name
        self.params = params
        self.definitions = definitions

        for param in params:
            self.input[param] = None

        for definition in self.definitions:
            self.output[definition] = None

    def step(self, graph: EventFlowGraph, state: State) -> Tuple[EventFlowNode, State]:
        pass

    def to_dict(self) -> Dict:
        return_dict = super().to_dict()
        return_dict["fun_name"] = self.fun_name
        return_dict["params"] = self.params
        return_dict["definitions"] = self.definitions

        return return_dict

    @staticmethod
    def construct(fun_type: FunctionType, dict: Dict):
        return InvokeSplitFun(
            fun_type, dict["id"], dict["fun_name"], dict["params"], dict["definitions"]
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

    def set_state_result(self, state: Dict):
        self.output[self.var_name] = state

    def step(self, graph: EventFlowGraph, state: State) -> Tuple[EventFlowNode, State]:
        state_get = state.get()

        # We copy the key, so that subsequent nodes can use it.
        state_get["__key"] == self.input["__key"]
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


class EventFlowDescriptor:
    pass


class EventFlow:
    def __init__(self, descriptor: EventFlowDescriptor):
        pass


class Event:
    from src.dataflow import Arguments

    __slots__ = "event_id", "fun_address", "event_type", "payload"

    def __init__(
        self,
        event_id: str,
        fun_address: FunctionAddress,
        event_type: EventType,
        payload: Dict,
    ):
        self.event_id: str = event_id
        self.fun_address: FunctionAddress = fun_address
        self.event_type: EventType = event_type
        self.payload: Dict = payload

    def get_arguments(self) -> Optional[Arguments]:
        if "args" in self.payload:
            return self.payload["args"]
        else:
            return None

    def copy(self, **kwargs) -> "Event":
        new_args = {}
        for key, value in kwargs.items():
            if key in self.__slots__:
                new_args[key] = value

        for key in self.__slots__:
            if key not in new_args:
                new_args[key] = getattr(self, key)

        return Event(**new_args)


class Action:
    def __init__(self, event_type: EventType):
        self.event_type = event_type
