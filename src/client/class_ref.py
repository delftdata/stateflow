from src.descriptors import ClassDescriptor, MethodDescriptor
from src.client.future import StateflowFuture
from src.dataflow.args import Arguments
from typing import List
from src.dataflow.event import Event, EventType, EventFlowNode
from src.client.stateflow_client import StateflowClient
import uuid
from src.serialization.json_serde import JsonSerializer


class MethodRef:
    """A wrapper/reference for a method from a stateful function/actor.
    This reference can be invoked, which will send an event to the client and return a futuree"
    """

    __slots__ = "method_name", "_class_ref", "method_desc"

    def __init__(
        self, method_name: str, class_ref: "ClassRef", method_desc: MethodDescriptor
    ):
        """Wraps around a method.

        :param method_name: the name of the method.
        :param class_ref: the reference to the class/actor/stateful function.
        :param method_desc: the descriptor of this method.
        """
        self.method_name = method_name
        self._class_ref = class_ref
        self.method_desc = method_desc

    def __call__(self, *args, **kwargs) -> StateflowFuture:
        """This is called when this 'method' is invoked.
        This will send an invocation event to the runtime. If it is a splitted function, it will send an eventflow.

        :param args: the args of the method.
        :param kwargs: the kwargs of the method.
        :return: a future.
        """
        if self.method_desc.is_splitted_function():
            return self._class_ref._invoke_flow(
                self.method_desc.flow_list,
                Arguments.from_args_and_kwargs(
                    self.method_desc.input_desc.get(), *args, **kwargs
                ),
            )

        return self._class_ref._invoke_method(
            self.method_name,
            Arguments.from_args_and_kwargs(
                self.method_desc.input_desc.get(), *args, **kwargs
            ),
        )


class ClassRef(object):
    """
    A wrapper/reference for a stateful function/actor.
    This reference can be used to invoke methods, get attributes and set attributes.

    This ClassRef assumes the instance already exists on the server/runtime.
    """

    from src.dataflow.event import FunctionAddress

    __slots__ = "_fun_addr", "_class_desc", "_attributes", "_methods", "_client"

    def __init__(
        self,
        fun_addr: FunctionAddress,
        class_desc: ClassDescriptor,
        client: StateflowClient,
    ):
        """Initializes a class reference.

        :param fun_addr: the address of this function (including key!).
        :param class_desc: the descriptor of this class.
        :param client: the client which is used to send and receive events to/from the runtime.
        """
        self._fun_addr = fun_addr
        self._class_desc = class_desc
        self._attributes = list(class_desc.state_desc.get_keys())
        self._methods = {
            method.method_name: method for method in class_desc.methods_dec
        }
        self._client = client

    def _invoke_method(self, method_name: str, args: Arguments) -> StateflowFuture:
        """Invokes a method of stateful function/actor.

        This method prepares the arguments and sets the correct payload.
        Finally the event is send to the runtime via the client. A StateflowFuture is returned,
        which will be completed when a response is received.

        :param method_name: the name of the method to invoke.
        :param args: the arguments of the method.
        :return: a stateflow future.
        """
        payload = {"args": args, "method_name": method_name}
        event_id: str = str(uuid.uuid4())

        invoke_method_event = Event(
            event_id, self._fun_addr, EventType.Request.InvokeStateful, payload
        )

        return self._client.send(invoke_method_event)

    def _invoke_flow(self, flow: List[EventFlowNode], args: Arguments):
        """Invokes a (splitted) method of stateful function/actor. This will invoke a so-called EventFlow.

        This method prepares the arguments and sets the correct payload.
        Finally the event is send to the runtime via the client. A StateflowFuture is returned,
        which will be completed when a response is received.

        :param flow: the EventFlow to invoke/traverse.
        :param args: the arguments of the method.
        :return: a stateflow future.
        """

        flow_dict = {}

        to_assign = list(args.get_keys())

        for f in flow:
            for arg in to_assign:
                if arg in f.input and not isinstance(args[arg], ClassRef):
                    f.input[arg] = args[arg]
                    to_assign.remove(arg)
                elif (
                    isinstance(args[arg], ClassRef)
                    and f.typ == EventFlowNode.REQUEST_STATE
                ):
                    f.set_request_key(args[arg]._fun_addr.key)
                    to_assign.remove(arg)

            flow_dict[f.id] = {"node": f, "status": "PENDING"}

        flow_dict[0]["status"] = "FINISHED"

        payload = {"flow": flow_dict, "current_flow": 1}
        event_id: str = str(uuid.uuid4())

        invoke_flow_event = Event(
            event_id, self._fun_addr, EventType.Request.EventFlow, payload
        )

        return self._client.send(invoke_flow_event)

    def get_attribute(self, attr: str) -> StateflowFuture:
        """Gets an attribute of this actor/stateful function.

        A GetState request event is send to the runtime.

        :param attr: the attribute to request. This attribute is part of the class 'state'.
        :return: a stateflow future.
        """
        payload = {"attribute": attr}
        event_id: str = str(uuid.uuid4())

        invoke_method_event = Event(
            event_id, self._fun_addr, EventType.Request.GetState, payload
        )

        return self._client.send(invoke_method_event)

    def set_attribute(self, attr: str, new) -> StateflowFuture:
        """Sets an attribute of this actor/stateful function.

        A SetState request event is send to the runtime.

        :param attr: the attribute to set. This attribute is part of the class 'state'.
        :param new: the value of this attribute.
        :return: a stateflow future.
        """
        payload = {"attribute": attr, "attribute_value": new}
        event_id: str = str(uuid.uuid4())

        invoke_method_event = Event(
            event_id, self._fun_addr, EventType.Request.UpdateState, payload
        )
        return self._client.send(invoke_method_event)

    def __getattr__(self, item):
        """Verifies which attribute of this object is retrieved.

        More specifically there are 3 scenarios which are handled:
        1. We get an attribute of the state of the class which is referenced. self.get_attribute is invoked.
        2. We get an method of the class which is referenced. A MethodRef is returned.
        3. We get an attribute of _this_ class ref (e.g. the client). The attribute is returned.


        :param item: the attribute requests.
        :return: the correct execution based on the 3 scenarios above.
        """
        if item in self._attributes:
            # print(f"Attribute access: {item}")
            return self.get_attribute(item)

        if item in self._methods.keys():
            # print(f"Method invocation: {item}")
            return MethodRef(item, self, self._methods[item])

        return object.__getattribute__(self, item)

    def __setattr__(self, key, value):
        """Sets an attribute.

        More specifically, there are 2 scenarios which are handled:
        1. The attribute key is in the __slots__, then we set it directly.
        2. 1 is not the case, then we invoke the set_attribute method which updates a state attribute on the runtime.

        :param key: the attribute name.
        :param value: the value to set for the given key.
        :return:
        """
        if key not in self.__slots__:
            return self.set_attribute(key, value)

        return object.__setattr__(self, key, value)

    def __str__(self):
        """Stringified version of this class reference.

        :return: string version of this reference.
        """
        return f"Class reference for {self._fun_addr.function_type.name} with key {self._fun_addr.key}."
