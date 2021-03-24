from typing import Dict, Any, List
from src.dataflow.stateful_fun import NoType


class MethodDescriptor:
    """A description of a class method."""

    def __init__(self, read_only, input_desc: "InputDescriptor"):
        self.read_only = read_only
        self.input_desc = input_desc


class InputDescriptor:
    """A description of the input parameters of a function.
    Includes types if declared. This class works like a dictionary.
    """

    def __init__(self, input_desc: Dict[str, Any]):
        self._input_desc = input_desc

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


class OutputDescriptor:


    def __init__(self, output_desc: List[Dict[str, Any]]):

