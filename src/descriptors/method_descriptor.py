from typing import Dict, Any, List, Set

import libcst as cst

from src.dataflow import *


class MethodDescriptor:
    """A description of a class method."""

    def __init__(
        self,
        method_name: str,
        read_only: bool,
        method_node: cst.FunctionDef,
        input_desc: "InputDescriptor",
        output_desc: "OutputDescriptor",
        external_attributes: Set[str],
        typed_declarations: Dict[str, str],
    ):
        self.method_name: str = method_name
        self.read_only: bool = read_only
        self.method_node: cst.FunctionDef = method_node
        self.input_desc: "InputDescriptor" = input_desc
        self.output_desc: "OutputDescriptor" = output_desc

        self._external_attributes = external_attributes
        self._typed_declarations = typed_declarations

        self.other_class_links: List = []

    def link_to_other_classes(self, descriptors: List):
        for d in descriptors:
            name = d.class_name

            if name in self._typed_declarations.values():
                # These are the declarations with a type equal to a class name.
                decl_with_type = [
                    key
                    for key, value in self._typed_declarations.items()
                    if value == name
                ]

                # We now check if this declaration is also attributed (i.e. get state, update state or invoke method).
                if len(set(decl_with_type).intersection(self._external_attributes)) > 0:
                    # Now we know this method is linked to another class or class method.
                    self.other_class_links.append(d)
                else:
                    # TODO; we have a type decl to another class, but it is not used? Maybe throw a warning/error.
                    pass

    def has_links(self) -> bool:
        return len(self.other_class_links) > 0


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

    def keys(self):
        return list(self._input_desc.keys())

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
