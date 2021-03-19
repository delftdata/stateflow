from typing import List, Tuple, Any, Optional, Dict
import libcst as cst
from dataflow.stateful_fun import StatefulFun, NoType
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
            self.self_attributes.append((node.target.attr.value, annotation))

    def visit_AugAssign(self, node: cst.AugAssign) -> Optional[bool]:
        if self.is_self(node.target) and m.matches(node.target.attr, m.Name()):
            self.self_attributes.append((node.target.attr.value, NoType))

    def visit_AssignTarget(self, node: cst.AssignTarget) -> None:
        if not m.matches(node, m.AssignTarget(target=m.Tuple())):
            if self.is_self(node.target) and m.matches(node.target.attr, m.Name()):
                self.self_attributes.append((node.target.attr.value, NoType))

        # We assume it is a Tuple now.
        if m.matches(node, m.AssignTarget(target=m.Tuple())):
            for element in node.target.elements:
                if (
                    m.matches(element, m.Element())
                    and self.is_self(element.value)
                    and m.matches(element.value.attr, m.Name())
                ):
                    self.self_attributes.append((element.value.attr.value, NoType))

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        if self.is_defined:  # We don't allow nested classes.
            raise AttributeError("Nested classes are not allowed.")

        self.is_defined = True
        self.class_name = helpers.get_full_name_for_node(node)

    def merge_self_attributes(self) -> Dict[str, any]:
        attributes = {}

        for var_name, typ in self.self_attributes:
            if var_name in attributes:
                if typ == NoType:
                    continue
                if typ != attributes[var_name]:
                    raise AttributeError(
                        f"Stateful Function {self.class_name} has two declarations of {var_name} with different types {typ} != {attributes[var_name]}."
                    )
                if attributes[var_name] == NoType:
                    attributes[var_name] = typ
            else:
                attributes[var_name] = typ

        for var_name, typ in attributes.items():
            if typ == NoType:
                print(f"{var_name} : NoType")
            else:
                print(f"{var_name} : {typ}")

        return attributes

    @staticmethod
    def create_stateful_fun(analyzed_tree: "ExtractStatefulFun") -> StatefulFun:
        class_attributes: Dict[str, any] = analyzed_tree.merge_self_attributes()
        return StatefulFun(class_name=analyzed_tree.class_name, state_desc=None)


class ExtractStatefulEvent(cst.CSTVisitor):
    def visit_Name(self, node: "Name") -> Optional[bool]:
        pass


print(List[int])
code = """
class Test:
    
    def fun(self):
        #self.z : Tuple[int, str]
        #self.x: str = 1
        #self.y += 0
        #self.x: str = "3"
        self.x, self.p = 3
        #self.r = 4
    
"""
import time

one = time.monotonic()
tree = cst.parse_module(code)
fun = ExtractStatefulFun(module_node=tree)
tree.visit(fun)
ExtractStatefulFun.create_stateful_fun(fun)
two = time.monotonic()
final = (two - one) * 1000
print(final)
