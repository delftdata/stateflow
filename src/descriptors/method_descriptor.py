from typing import Dict, Any, List
from src.dataflow.args import Arguments


class MethodDescriptor:
    """A description of a class method."""

    def __init__(
        self,
        method_name: str,
        read_only: bool,
        input_desc: "InputDescriptor",
        output_desc: "OutputDescriptor",

    ):
        self.method_name: str = method_name
        self.read_only: bool = read_only
        self.input_desc: "InputDescriptor" = input_desc
        self.output_desc: "OutputDescriptor" = output_desc


class InputDescriptor:
    """A description of the input parameters of a function.
    Includes types if declared. This class works like a dictionary.
    """

    def __init__(self, input_desc: Dict[str, Any]):
        self._input_desc: Dict[str, Any] = input_desc

    def __contains__(self, item):
        return item in self._input_desc

    def __delitem__(self, key):
        del self._input_desc[key]

    def __getitem__(self, item):
        return self._input_desc[item]

    def __setitem__(self, key, value):
        self._input_desc[key] = value

    def __str__(self):
        return self._input_desc.__str__()

    def __hash__(self):
        return self._input_desc.__hash__()

    def __eq__(self, other):
        return self._input_desc == other

    def get(self) -> Dict[str, Any]:
        return self._input_desc

    def match(self, args: Arguments) -> bool:
        return args.get_keys() == self._input_desc.keys()

    def __str__(self):
        return str(list(self._input_desc.keys()))


class OutputDescriptor:
    """A description of the output of a function.
    Includes types if declared. Since a function can have multiple returns,
    we store each return in a list.

    A return is stored as a List of types. We don't store the return variable,
    because we do not care about it. We only care about the amount of return variables
    and potentially its type.
    """

    def __init__(self, output_desc: List[List[Any]]):
        self.output_desc: List[List[Any]] = output_desc

    def num_returns(self):
        """The amount of (potential) outputs.

        If a method has multiple return paths, these are stored separately.
        This function returns the amount of these paths.

        :return: the amount of returns.
        """
        return len(self.output_desc)
