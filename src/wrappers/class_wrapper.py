from src.dataflow.state import State
from typing import List, Optional, Any, Dict, Union, Tuple
from src.descriptors import ClassDescriptor, MethodDescriptor
from src.dataflow.args import Arguments


class InvocationResult:
    def __init__(
        self,
        updated_state: Optional[State],
        return_results: Optional[Union[Any, List[Any]]],
    ):
        self.updated_state: Optional[State] = updated_state
        self.return_results: Optional[Union[Any, List[Any]]] = return_results

    def results_as_list(self) -> List[Any]:
        if isinstance(self.return_results, tuple):
            return list(self.return_results)
        return [self.return_results]


class FailedInvocation(InvocationResult):
    def __init__(self, message: str):
        super().__init__(updated_state=None, return_results=None)
        self.message: str = message

    def __str__(self):
        return self.message


class ClassWrapper:
    """Wrapper around a class implementation.

    This is a wrapper around a class implementation.
    It offers two methods:
    1. invoke: this invokes a method of a class and returns the updated state + the method results.
    2. init_class: this calls the __init__ of a class and also evaluates the __key__ method.
       This needs to be separated from a normal invocation, because we assume that for invoke the state already exists.
    """

    def __init__(self, cls, class_desc: ClassDescriptor):
        self.cls = cls
        self.class_desc: ClassDescriptor = class_desc
        self.methods_desc: Dict[str, MethodDescriptor] = {
            m.method_name: m for m in class_desc.methods_dec
        }

    def init_class(self, arguments: Arguments) -> InvocationResult:
        """Initializes the wrapped class.

        Calls the __init__ of a class and evaluates the key. We need to do this separately, because a stateful function
        will be partitioned according to its key.

        :param arguments: the arguments of the initialization.
        :return: either a successful InvocationResult or a FailedInvocation.
                The InvocationResult stores the instance key in its `return_results`.
        """
        init_method: MethodDescriptor = self.methods_desc["__init__"]

        # TODO: Consider removing this, we should check this maybe client side or not at all..
        # Especially if we want performance..
        if not init_method.input_desc.match(arguments):
            return FailedInvocation(
                "Invocation arguments do not match input description of the method.\n"
                f"Expected {init_method.input_desc}, but got {list(arguments.get_keys())}."
            )

        try:
            # Get class and compute it's key.
            class_instance = self.cls(**arguments.get())
            class_key = class_instance.__key__()

            return InvocationResult(
                self._get_updated_state(class_instance), [class_key]
            )
        except Exception as e:
            return FailedInvocation(
                f"Exception occurred during creation of {self.class_desc.class_name}: {e}."
            )

    def find_method(self, method_name: str) -> Optional[MethodDescriptor]:
        """Finds a method in the descriptors.

        This methods tries to find the correct descriptor for a method name.
        If it can't be found None is returned. Assumes there is only 1 MethodDescriptor
        per method name.

        :param method_name: the method to find.
        :return: a MethodDescriptor or None.
        """
        if method_name not in self.methods_desc:
            return None

        return self.methods_desc[method_name]

    def _get_updated_state(self, instance: Any) -> State:
        # Get the updated state.
        updated_state = {}
        for k in self.class_desc.state_desc.get_keys():
            updated_state[k] = getattr(instance, k)

        return State(updated_state)

    def _call_method(
        self, instance: Any, method_name: str, arguments: Arguments
    ) -> Any:
        method_to_call = getattr(instance, method_name)
        return method_to_call(**arguments.get())

    def invoke(
        self, method_name: str, state: State, arguments: Arguments
    ) -> InvocationResult:
        """Invokes a method on this wrapped class.

        Will perform the following procedure:
        1. Find the correct descriptor of the method, given the method name.
        2. Constructs the class and sets the state (without invoking __init__).
        3. Execute method with arguments.
        4. Return method output and resulting state in an InvocationResult.

        In case of failure, we will return a FailedInvocation.
        We assume that arguments are already checked on the client side, due to performance reasons.

        :param method_name: the method to invoke.
        :param state: the state of the class.
        :param arguments: the arguments of the invocation.
        :return: either a successful InvocationResult or a FailedInvocation.
        """
        try:
            # Construct a new class.
            constructed_class = self.cls.__new__(self.cls)

            # Set state of class.
            for k in self.class_desc.state_desc.get_keys():
                setattr(constructed_class, k, state[k])

            # Call the method.
            method_result = self._call_method(constructed_class, method_name, arguments)

            # Return the results.
            return InvocationResult(
                self._get_updated_state(constructed_class), method_result
            )
        except Exception as e:
            return FailedInvocation(f"Exception occurred during invocation: {e}.")

    def invoke_with_instance(
        self, method_name: str, instance: Any, arguments: Arguments
    ) -> InvocationResult:
        """Invokes a method on this wrapped class.

        Will perform the following procedure:
        1. Execute method with arguments.
        2. Return method output in an InvocationResult and the updated instance.

        In case of failure, we will return a FailedInvocation.
        We assume that arguments are already checked on the client side, due to performance reasons.

        :param method_name: the method to invoke.
        :param instance: the instance of this class.
        :param arguments: the arguments of the invocation.
        :return: either a successful InvocationResult or a FailedInvocation.
        """
        try:
            # Call the method.
            method_result = self._call_method(instance, method_name, arguments)

            # Return the results.
            return InvocationResult(self._get_updated_state(instance), method_result)
        except Exception as e:
            return FailedInvocation(f"Exception occurred during invocation: {e}.")

    def invoke_return_instance(
        self, method_name: str, state: State, arguments: Arguments
    ) -> Union[InvocationResult, Tuple[InvocationResult, Any]]:
        """Invokes a method on this wrapped class.

        Will perform the following procedure:
        1. Find the correct descriptor of the method, given the method name.
        2. Constructs the class and sets the state (without invoking __init__).
        3. Execute method with arguments.
        4. Return method output and in an InvocationResult + the instance.

        In case of failure, we will return a FailedInvocation.
        We assume that arguments are already checked on the client side, due to performance reasons.

        :param method_name: the method to invoke.
        :param state: the state of the class.
        :param arguments: the arguments of the invocation.
        :return: either a successful InvocationResult or a FailedInvocation + the instance.
        """
        try:
            # Construct a new class.
            constructed_class = self.cls.__new__(self.cls)

            # Set state of class.
            for k in self.class_desc.state_desc.get_keys():
                setattr(constructed_class, k, state[k])

            # Call the method.
            method_result = self._call_method(constructed_class, method_name, arguments)

            # Return the results.
            return (
                InvocationResult(
                    self._get_updated_state(constructed_class), method_result
                ),
                constructed_class,
            )
        except Exception as e:
            return FailedInvocation(f"Exception occurred during invocation: {e}.")

    def __str__(self):
        return f"ClassWrapper for the class {self.class_desc.class_name}."
