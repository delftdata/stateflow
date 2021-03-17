from typing import List, Tuple, Any, Optional
import libcst as cst
from dataflow.stateful_fun import StatefulFun
import libcst.matchers as m


class ExtractStatefulFun(cst.CSTVisitor):
    def __init__(self):
        self.is_defined: bool = False
        self.class_name: str = None

        self.self_attributes: List[Tuple[str, Any]] = []

    def extract_types(self, node: cst.Annotation) -> Any:
        pass

    def is_self(self, node: cst.CSTNode) -> bool:
        if m.matches(node, m.Attribute(value=m.Name(value="self"))):
            return True

        return False

    def visit_AnnAssign(self, node: cst.AnnAssign) -> Optional[bool]:
        if self.is_self(node.target) and m.matches(node.target.attr, m.Name()):
            print(node.annotation.annotation)
            print(
                f"Found class variable {node.target.attr.value} with type {node.annotation.annotation.value}"
            )

    def visit_AugAssign(self, node: cst.AugAssign) -> Optional[bool]:
        if self.is_self(node.target):
            print(f"Found class variable {node.attr}.")

    def visit_Assign(self, node: cst.Assign) -> Optional[bool]:
        for target in node.targets:
            print("HERE")
            if self.is_self(target):
                print(f"Jeej {target}")

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        if self.is_defined:  # We don't allow nested classes.
            raise AttributeError("Nested classes are not allowed.")

        self.is_defined = True
        self.class_name = node.name.value

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
        self.x: List[int] = 1
        self.y = 0
    
"""
fun = ExtractStatefulFun()
tree = cst.parse_module(code)
# print(tree)
tree.visit(fun)
