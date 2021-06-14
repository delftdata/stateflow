from typing import Dict, Any, List, Set, Optional, Tuple

import libcst as cst

from src.dataflow.args import Arguments
import re


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
        write_to_self_attributes: Set[str],
    ):
        self.method_name: str = method_name
        self.read_only: bool = read_only
        self.method_node: cst.FunctionDef = method_node
        self.input_desc: "InputDescriptor" = input_desc
        self.output_desc: "OutputDescriptor" = output_desc

        self._external_attributes = external_attributes
        self._typed_declarations = typed_declarations

        self.write_to_self_attributes: Set[str] = write_to_self_attributes

        self.other_class_links: List = []

        self.statement_blocks = []
        self.flow_list = []

    def is_splitted_function(self) -> bool:
        return len(self.statement_blocks) > 0

    def split_function(self, blocks, fun_addr):
        from src.dataflow.event_flow import (
            EventFlowNode,
            StartNode,
        )

        self.statement_blocks = blocks.copy()
        self.flow_list: List[EventFlowNode] = []

        # Build start of the flow.
        flow_start: EventFlowNode = StartNode(0, fun_addr)
        latest_node_id: int = flow_start.id
        self.flow_list.append(flow_start)

        # A mapping from Block to EventFlowNode.
        # Used to correctly build a EventFlowGraph
        flow_mapping = {block.block_id: None for block in self.statement_blocks}

        # print("Now splitting function.")
        for block in self.statement_blocks:
            flow_nodes: List[EventFlowNode] = block.build_event_flow_nodes(
                latest_node_id
            )
            self.flow_list.extend(flow_nodes)
            if block.block_id == 0 or block.block_id == 1:
                pass
                # print(f"flow nodes {flow_nodes}")
            flow_mapping[block.block_id] = flow_nodes

            latest_node_id = self.flow_list[-1].id

            # print(
            #     f"Now computed flow nodes for {block.block_id} with length {len(flow_nodes)}"
            # )

        # print(f"Mapping {flow_mapping}")

        # Now that we got all flow nodes built, we can properly link them to each other.
        for block in self.statement_blocks:
            flow_nodes = flow_mapping[block.block_id]
            # print(f"Now looking at {block.block_id}")

            # Get next block of this current block.
            for next_block in block.next_block:
                # print(f"Block {block.block_id} is linked to {next_block.block_id}")
                next_flow_node_list = flow_mapping[next_block.block_id]
                if flow_nodes is None or next_flow_node_list is None:
                    raise RuntimeError(
                        f"Empty block flow nodes: {block.block_id}"
                        f"{block.code()}"
                        f"{flow_nodes}"
                        f"Next block: {next_block.block_id}"
                        f"{next_block.code()}"
                        f"{next_flow_node_list}"
                        f"{flow_mapping}"
                    )

                flow_nodes[-1].resolve_next(next_flow_node_list, next_block)

                # We won't set the previous, this is what we will do dynamically.
                # Based on the path that is traversed, we know what the previous was.

        flow_start.set_next(self.flow_list[1].id)

    def get_typed_params(self):
        # TODO Improve this. Very ambiguous name.
        params: List[str] = []
        for name, typ in self.input_desc.get().items():
            if typ in self.other_class_links:
                params.append(name)

        return params

    def _is_linked(self, name: str, types: Dict[str, str]) -> Tuple[bool, List[str]]:
        r = re.compile(f"^({name}|List\\[{name}\\])$")

        linked_vars = []
        for name, typ in types.items():
            if r.match(typ):
                linked_vars.append(name)

        return len(linked_vars) > 0, linked_vars

    def link_to_other_classes(self, descriptors: List):
        for d in descriptors:
            name = d.class_name

            is_linked, links = self._is_linked(name, self._typed_declarations)
            if is_linked:
                # We now check if this declaration is also attributed (i.e. get state, update state or invoke method).
                if len(set(links).intersection(self._external_attributes)) > 0:
                    # Now we know this method is linked to another class or class method.
                    self.other_class_links.append(d)
                elif set(links).intersection(set(self.input_desc.keys())):
                    # The List is given as parameter.
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
