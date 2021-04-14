from typing import Dict, Any, List, Set, Optional

import libcst as cst

from src.dataflow.args import Arguments
from src.dataflow.event import (
    EventFlowNode,
    StartNode,
    RequestState,
    FunctionType,
    InvokeSplitFun,
    ReturnNode,
    InvokeExternal,
)


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

        self.statement_blocks: List["StatementBlock"] = []
        self.flow_start: EventFlowNode = None

    def is_splitted_function(self) -> bool:
        return len(self.statement_blocks) > 0

    def split_function(
        self, class_name: str, blocks: List["StatementBlock"], descriptors: List
    ):
        self.statement_blocks = blocks

        # 'build' action flow.
        # 1. Get state of statement block 0
        # 2. Execute statement block 0
        # 3. D

        # InputDescriptor will match the input of block[0]
        # We will check if we need to obtain state of another class.
        flow_start: EventFlowNode = StartNode()
        flow: EventFlowNode = flow_start

        for input, input_type in self.input_desc.get().items():
            matched_type = self._match_type(input_type, descriptors)

            if matched_type:
                flow = flow.set_next(
                    RequestState(FunctionType.create(matched_type), input)
                )

        for block in blocks:
            if block.block_id == 0:
                split_node = InvokeSplitFun(
                    FunctionType.create(self._match_type(class_name, descriptors)),
                    block.fun_name(),
                    list(self.input_desc.keys()),
                    list(block.definitions),
                )
                if block.returns > 0:
                    return_node = ReturnNode()
                    flow = flow.set_next([split_node, return_node])[0]
                else:
                    flow = flow.set_next(split_node)[0]

                flow = flow.set_next(
                    InvokeExternal(
                        FunctionType.create(
                            self._match_type(
                                block.class_invoked.class_name, descriptors
                            )
                        ),
                        block.class_invoked.class_name,
                        block.method_invoked,
                        block.get_call_arguments(),
                    )
                )

            elif block.last_block:
                split_node = InvokeSplitFun(
                    FunctionType.create(self._match_type(class_name, descriptors)),
                    block.fun_name(),
                    list(self.input_desc.keys()),
                    [],
                )

                flow = flow.set_next(split_node)
                flow = flow.set_next(ReturnNode())

        self.flow_start = flow_start

    def _match_type(self, input_type, descriptors) -> Optional:
        descriptors_filter = [
            desc for desc in descriptors if desc.class_name == input_type
        ]

        if len(descriptors_filter) > 0:
            return descriptors_filter[0]

        return None

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
