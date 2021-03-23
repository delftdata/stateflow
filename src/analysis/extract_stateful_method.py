import libcst as cst
from typing import List, Tuple, Any, Optional
from src.analysis import ast_utils
import libcst.matchers as m
from src.dataflow.stateful_fun import NoType


class ExtractStatefulMethod(cst.CSTVisitor):
    """Visits a FunctionDef and extracts information to create a MethodWrapper.
    Assumes FunctionDef is part of ClassDef."""

    def __init__(self, class_node: cst.CSTNode, fun_node: cst.CSTNode):
        self.class_node = class_node
        self.fun_node = fun_node
        self.self_attributes: List[Tuple[str, Any]] = []

    def visit_AnnAssign(self, node: cst.AnnAssign) -> Optional[bool]:
        if ast_utils.is_self(node.target) and m.matches(node.target.attr, m.Name()):
            annotation = ast_utils.extract_types(self.class_node, node.annotation)
            self.self_attributes.append((node.target.attr.value, annotation))

    def visit_AugAssign(self, node: cst.AugAssign) -> Optional[bool]:
        if ast_utils.is_self(node) and m.matches(node.target.attr, m.Name()):
            self.self_attributes.append((node.target.attr.value, NoType))

    def visit_AssignTarget(self, node: cst.AssignTarget) -> None:
        if not m.matches(node, m.AssignTarget(target=m.Tuple())):
            if ast_utils.is_self(node.target) and m.matches(node.target.attr, m.Name()):
                self.self_attributes.append((node.target.attr.value, NoType))

        # We assume it is a Tuple now.
        if m.matches(node, m.AssignTarget(target=m.Tuple())):
            for element in node.target.elements:
                if (
                    m.matches(element, m.Element())
                    and ast_utils.is_self(element.value)
                    and m.matches(element.value.attr, m.Name())
                ):
                    self.self_attributes.append((element.value.attr.value, NoType))

    def visit_Name(self, node: cst.Name) -> Optional[bool]:
        pass
