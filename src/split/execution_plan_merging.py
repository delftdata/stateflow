import copy

from src.descriptors import MethodDescriptor, ClassDescriptor
from src.dataflow.event_flow import (
    EventFlowNode,
    InvokeExternal,
    FunctionType,
    StartNode,
)
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass


@dataclass
class ReplaceRequest:
    node_to_replace: InvokeExternal
    method_to_insert: MethodDescriptor
    nest_level: int


class ExecutionPlanMerger:
    def __init__(self, class_descriptors: List[ClassDescriptor]):
        self.class_descriptors = class_descriptors
        self.method_descriptors: List[MethodDescriptor] = []
        self.method_to_fun_type = {}

        for c_desc in self.class_descriptors:
            for m_desc in c_desc.methods_dec:
                self.method_descriptors.append(m_desc)
                self.method_to_fun_type[m_desc] = c_desc.to_function_type()

    def _is_match(self, flow_node: EventFlowNode) -> Optional[MethodDescriptor]:
        """Matches an InvokeExternal flow node to the correct method descriptor.

        :param flow_node: the flow node.
        :return: None if no method descriptor is found
        """
        if flow_node.typ != EventFlowNode.INVOKE_EXTERNAL:
            return None

        method_name: str = flow_node.fun_name
        fun_type: FunctionType = flow_node.fun_type

        # Find method which matches the name and the function type.
        for method_desc in self.method_descriptors:
            if (
                method_name == method_desc.method_name
                and self.method_to_fun_type[method_desc] == fun_type
                and len(method_desc.flow_list) > 0
            ):
                return method_desc

        return None

    def _find_replace_request(
        self, current_node: InvokeExternal, requests: List[ReplaceRequest]
    ) -> Optional[ReplaceRequest]:
        for req in requests:
            if req.node_to_replace == current_node:
                return req

        return None

    def _node_by_id(self, node_id: int, nodes: List[EventFlowNode]) -> EventFlowNode:
        for n in nodes:
            if n.id == node_id:
                return n

    def replace_and_merge(self, flow_list: List[EventFlowNode]):
        flow_list, lookup_table = self.replace_nested_invoke(flow_list)

        return self.flatten(lookup_table)

    def flatten(self, t):
        return [item for sublist in t for item in sublist]

    def replace_nested_invoke(
        self, flow_list: List[EventFlowNode], current_block_id: int = 0
    ) -> Tuple[List[EventFlowNode], List[List[EventFlowNode]]]:
        if len(flow_list) == 0:
            return flow_list, []

        flow_list: List[EventFlowNode] = copy.deepcopy(flow_list)
        replacement_nodes: List[ReplaceRequest] = self.mark_replacement_nodes(flow_list)

        # For each method_id we have a lookup table for which we can find the original node id's and the new node id's.
        lookup_table: List[List[EventFlowNode]] = [flow_list]

        stack: List[EventFlowNode] = [flow_list[0]]
        discovered: List[EventFlowNode] = []

        id_to_node: Dict[int, EventFlowNode] = {}
        unlinked_next_nodes: Dict[int, List[EventFlowNode]] = {}

        while len(stack) > 0:
            current_node: EventFlowNode = stack.pop()
            print(f"Current node with id {current_node.id}")

            # We already visited this node.
            if current_node in discovered:
                continue

            print(current_node)
            original_node_id: int = current_node.id
            next_nodes: List[EventFlowNode] = list(
                filter(
                    None, [self._node_by_id(n, flow_list) for n in current_node.next]
                )
            )

            # Find if we need to 'replace' this node.
            replace_request: Optional[ReplaceRequest] = self._find_replace_request(
                current_node, replacement_nodes
            )
            if replace_request:
                event_flow_nodes, nested_lookup_table = self.replace_nested_invoke(
                    replace_request.method_to_insert.flow_list, current_block_id
                )

                assert len(event_flow_nodes) > 0
                assert len(nested_lookup_table) > 0

                from src.util.dataflow_visualizer import visualize_flow

                print("JOE")
                visualize_flow(event_flow_nodes)

                # Update state.
                current_block_id += len(self.flatten(nested_lookup_table))
                lookup_table.extend(nested_lookup_table)

                # Now we 'replace' the InvokeExternal with the resulting flow.

                # We stitch the start node of this flow, to the incoming edges of the InvokeExternal.
                start_node: StartNode = event_flow_nodes[0]
                print(f"StartNode == {isinstance(start_node, StartNode)}")

                to_link_to_start: List[EventFlowNode] = [
                    node for node in discovered if original_node_id in node.next
                ]

                # These can already be linked.
                for node in to_link_to_start:
                    node.set_next(start_node.id)

                # Now we have to link the return nodes of the nested flow, to the 'next' node.
                to_link_return: List[EventFlowNode] = [
                    node
                    for node in event_flow_nodes
                    if node.typ == EventFlowNode.RETURN
                ]
                for return_node in to_link_return:
                    unlinked_next_nodes[return_node.id] = next_nodes
                    id_to_node[return_node.id] = return_node

                # Add next nodes to the stack
                stack.extend(next_nodes)
            else:
                current_node.id = current_block_id
                current_block_id += 1

                unlinked_next_nodes[current_node.id] = next_nodes
                id_to_node[current_node.id] = current_node

                stack.extend(next_nodes)

        # Link 'unlinked' nodes.
        for node_id, next_nodes in unlinked_next_nodes.items():
            node: EventFlowNode = id_to_node[node_id]

            node.next = []
            node.set_next([n.id for n in next_nodes])

        return flow_list, lookup_table

    def mark_replacement_nodes(
        self, flow_list: List[EventFlowNode], nest_level: int = 0
    ) -> List[Tuple[InvokeExternal, MethodDescriptor]]:
        if len(flow_list) == 0:
            return []

        replace_requests: List[ReplaceRequest] = []

        for flow_node in flow_list:
            is_match: Optional[MethodDescriptor] = self._is_match(flow_node)
            if not is_match:  # if no match, continue to next node.
                continue

            replace_requests.append(ReplaceRequest(flow_node, is_match, nest_level))

            # Recursively find nested calls which we need to replace.
            calls_to_replace: List[ReplaceRequest] = self.mark_replacement_nodes(
                is_match.flow_list, nest_level + 1
            )
            replace_requests.extend(calls_to_replace)

        return replace_requests
