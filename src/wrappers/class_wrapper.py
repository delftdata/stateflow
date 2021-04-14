from src.dataflow.state import State
from typing import List, Optional, Any, Dict, Union
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

        if not init_method.input_desc.match(arguments):
            return FailedInvocation(
                "Invocation arguments do not match input description of the method.\n"
                f"Expected {init_method.input_desc}, but got {list(arguments.get_keys())}."
            )

        try:
            # Get class and compute it's key.
            class_instance = self.cls(**arguments.get())
            class_key = class_instance.__key__()

            # Get the updated state.
            updated_state = {}
            for k in self.class_desc.state_desc.get_keys():
                updated_state[k] = getattr(class_instance, k)

            return InvocationResult(State(updated_state), [class_key])
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
        method_desc: Optional[MethodDescriptor] = self.find_method(method_name)

        # If there exists no method descriptor, we can't handle this invocation.
        # if not method_desc:
        #     return FailedInvocation(
        #         f'Method "{method_name}" does not exist in class {self.class_desc.class_name}. Available methods are: {list(self.methods_desc.keys())}'
        #     )

        try:
            # Construct a new class.
            constructed_class = self.cls.__new__(self.cls)

            # Set state of class.
            for k in self.class_desc.state_desc.get_keys():
                setattr(constructed_class, k, state[k])

            # Call the method.
            method_to_call = getattr(constructed_class, method_name)
            method_result = method_to_call(**arguments.get())

            # Get the updated state.
            updated_state = {}
            for k in self.class_desc.state_desc.get_keys():
                updated_state[k] = getattr(constructed_class, k)

            # Return the results.
            return InvocationResult(State(updated_state), method_result)
        except Exception as e:
            return FailedInvocation(f"Exception occurred during invocation: {e}.")

    def __str__(self):
        return f"ClassWrapper for the class {self.class_desc.class_name}."
