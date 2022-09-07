from typing import Dict, Optional


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

    def get_safe_full_name(self):
        return f"{self.namespace}_{self.name}"

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

    def to_address(self) -> "FunctionAddress":
        return FunctionAddress(self, None)

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
