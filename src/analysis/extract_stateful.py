from typing import List, Tuple, Any, Optional
import libcst as cst
from dataflow.stateful_fun import StatefulFun
import libcst.matchers as m
import libcst.helpers as helpers


class ExtractStatefulFun(cst.CSTVisitor):
    def __init__(self, module_node: cst.CSTNode):
        self.module_node = module_node
        self.is_defined: bool = False
        self.class_name: str = None

        self.self_attributes: List[Tuple[str, Any]] = []

    def extract_types(self, node: cst.Annotation) -> Any:
        return eval(self.module_node.code_for_node(node.annotation))

    def is_self(self, node: cst.CSTNode) -> bool:
        if m.matches(node, m.Attribute(value=m.Name(value="self"))):
            return True

        return False

    def visit_AnnAssign(self, node: cst.AnnAssign) -> Optional[bool]:
        if self.is_self(node.target) and m.matches(node.target.attr, m.Name()):
            annotation = self.extract_types(node.annotation)
            print(
                f"Found class variable {node.target.attr.value} with type {annotation}."
            )

    def visit_AugAssign(self, node: cst.AugAssign) -> Optional[bool]:
        if self.is_self(node.target) and m.matches(node.target.attr, m.Name()):
            print(f"Found class variable {node.target.attr.value} without a type hint.")

    def visit_AssignTarget(self, node: cst.AssignTarget) -> None:
        if not m.matches(node, m.AssignTarget(target=m.Tuple())):
            if self.is_self(node.target) and m.matches(node.target.attr, m.Name()):
                print(
                    f"Found class variable {node.target.attr.value} without a type hint."
                )

        # Cover tuples.

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        if self.is_defined:  # We don't allow nested classes.
            raise AttributeError("Nested classes are not allowed.")

        self.is_defined = True
        self.class_name = helpers.get_full_name_for_node(node)

    @staticmethod
    def create_stateful_fun(analyzed_tree: "ExtractStatefulFun") -> StatefulFun:
        return StatefulFun(class_name=analyzed_tree.class_name)


class ExtractStatefulEvent(cst.CSTVisitor):
    def visit_Name(self, node: "Name") -> Optional[bool]:
        pass


print(List[int])
code = """
class Test:
    
    def fun(self):
        self.z : Tuple[int, str]
        self.x: List[int] = 1
        self.y += 0
        self.x: str = "3"
        self.x, self.p = 3
        self.r = 4
    
"""
tree = cst.parse_module(code)
fun = ExtractStatefulFun(module_node=tree)
# print(tree)
tree.visit(fun)
