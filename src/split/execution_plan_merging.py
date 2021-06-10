from src.descriptors import MethodDescriptor, ClassDescriptor
from src.dataflow.event_flow import EventFlowNode, InvokeExternal, FunctionType
from typing import List, Optional, Tuple
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
            ):
                return method_desc

        return None

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
