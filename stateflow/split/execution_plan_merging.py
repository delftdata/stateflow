import copy

from stateflow.descriptors.class_descriptor import MethodDescriptor, ClassDescriptor
from stateflow.dataflow.event_flow import (
    EventFlowNode,
    InvokeExternal,
    FunctionAddress,
    InvokeConditional,
    InvokeFor,
    StartNode,
    Null,
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

    def execute_merge(self):
        updates: Dict[MethodDescriptor, List[EventFlowNode]] = {}
        for method in self.method_descriptors:
            if method.is_splitted_function():
                updates[method] = self.replace_and_merge(method.flow_list)

        for method, flow_list in updates.items():
            method.flow_list = flow_list

    def _is_match(self, flow_node: EventFlowNode) -> Optional[MethodDescriptor]:
        """Matches an InvokeExternal flow node to the correct method descriptor.

        :param flow_node: the flow node.
        :return: None if no method descriptor is found
        """
        if flow_node.typ != EventFlowNode.INVOKE_EXTERNAL:
            return None

        method_name: str = flow_node.fun_name
        fun_addr: FunctionAddress = flow_node.fun_addr

        # Find method which matches the name and the function type.
        for method_desc in self.method_descriptors:
            if (
                method_name == method_desc.method_name
                and self.method_to_fun_type[method_desc] == fun_addr.function_type
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

    def _node_by_id(
        self, node_id: int, nodes: List[EventFlowNode]
    ) -> Optional[EventFlowNode]:
        for n in nodes:
            if n.id == node_id:
                return n

        return None

    def replace_and_merge(
        self,
        flow_list: List[EventFlowNode],
        current_block_id: int = 0,
        current_method_id: int = 0,
    ) -> EventFlowNode:
        flow_list, lookup_table = self.replace_nested_invoke(
            flow_list, current_block_id, current_method_id
        )
        return self.flatten(lookup_table)

    def flatten(self, t):
        return [item for sublist in t for item in sublist]

    def replace_nested_invoke(
        self,
        flow_list: List[EventFlowNode],
        current_block_id: int = 0,
        current_method_id: int = 0,
    ) -> Tuple[List[EventFlowNode], List[List[EventFlowNode]]]:
        if len(flow_list) == 0:
            return flow_list, []

        flow_list: List[EventFlowNode] = copy.deepcopy(flow_list)
        replacement_nodes: List[ReplaceRequest] = self.mark_replacement_nodes(flow_list)

        for node in flow_list:
            node.next = [self._node_by_id(n, flow_list) for n in node.next]

            if isinstance(node, InvokeConditional):  # True and False
                node.if_true_node = self._node_by_id(node.if_true_node, flow_list)
                node.if_false_node = self._node_by_id(node.if_false_node, flow_list)

            if isinstance(node, InvokeFor):
                node.for_body_node = self._node_by_id(node.for_body_node, flow_list)
                node.else_node = self._node_by_id(node.else_node, flow_list)

        # For each method_id we have a lookup table for which we can find the original node id's and the new node id's.
        lookup_table: List[List[EventFlowNode]] = [flow_list]

        stack: List[EventFlowNode] = [flow_list[0]]
        discovered: List[EventFlowNode] = []

        nodes_to_relink: List[EventFlowNode] = []
        replaced: int = 0

        while len(stack) > 0:
            current_node: EventFlowNode = stack.pop()
            current_node.method_id = current_method_id

            # We already visited this node.
            if current_node in discovered:
                continue

            discovered.append(current_node)

            # Find if we need to 'replace' this node.
            replace_request: Optional[ReplaceRequest] = self._find_replace_request(
                current_node, replacement_nodes
            )
            if replace_request:
                # print("IF CLAUSE")
                replaced += 1
                new_nodes = self.replace_and_merge(
                    replace_request.method_to_insert.flow_list,
                    current_block_id,
                    current_method_id + replaced + 1,
                )

                from stateflow.util.dataflow_visualizer import visualize_flow

                # print(f"Now replaced {current_node} at level {current_method_id}")
                visualize_flow(new_nodes)

                assert len(new_nodes) > 0
                assert new_nodes[0].id == current_block_id

                # Update state.
                current_block_id += len(new_nodes)
                lookup_table.append(new_nodes)

                # Now we 'replace' the InvokeExternal with the resulting flow.

                # We stitch the start node of this flow, to the incoming edges of the InvokeExternal.
                start_node: StartNode = new_nodes[0]
                assert isinstance(start_node, StartNode)

                # This node needs to copy the required input from the InvokeExternal.
                for arg in current_node.args:
                    start_node.output[arg] = Null

                to_link_to_start: List[EventFlowNode] = [
                    node for node in discovered if current_node in node.next
                ]

                # These can already be linked.
                for node in to_link_to_start:
                    node.set_next(start_node)
                    node.next = [n for n in node.next if n != current_node]

                # Now we have to link the return nodes of the nested flow, to the 'next' node.
                to_link_return: List[EventFlowNode] = [
                    node
                    for node in new_nodes
                    if node.typ == EventFlowNode.RETURN and node.next == []
                ]

                for return_node in to_link_return:
                    return_node.return_name = current_node.get_output_name()
                    return_node.next = current_node.next
                    nodes_to_relink.append(return_node)

                flow_list.remove(current_node)

                # Add next nodes to the stack
                stack.extend(current_node.next)
            else:
                current_node.id = current_block_id
                current_block_id += 1

                stack.extend(current_node.next)

        for node in flow_list:
            if isinstance(node, InvokeConditional):
                node.if_true_node = node.next[0].id
                node.if_false_node = node.next[1].id

            if isinstance(node, InvokeFor):
                node.for_body_node = node.for_body_node.id
                node.else_node = node.else_node.id if node.else_node else -1

            node.next = [n.id for n in node.next]

        for node in nodes_to_relink:
            if isinstance(node, InvokeConditional):
                node.if_true_node = node.next[0].id
                node.if_false_node = node.next[1].id

            if isinstance(node, InvokeFor):
                node.for_body_node = node.for_body_node.id
                node.else_node = node.else_node.id if node.else_node else -1

            node.next = [n.id for n in node.next]

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
