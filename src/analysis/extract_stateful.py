from typing import List, Tuple, Dict, Optional
import libcst as cst
from ..dataflow.stateful_fun import StatefulFun


class ExtractStatefulFun(cst.CSTVisitor):
    def __init__(self):
        self.is_defined = False
        self.class_name = None

    def visit_ClassDef(self, node: cst.ClassDef):
        if self.is_defined:  # We don't allow nested classes.
            raise AttributeError("Nested classes are not allowed.")

        self.is_defined = True
        self.class_name = node.name.value

    @staticmethod
    def create_stateful_fun(analyzed_tree: "ExtractStatefulFun") -> StatefulFun:
        return StatefulFun(class_name=analyzed_tree.class_name)


class ExtractStatefulEvent(cst.CSTVisitor):
    pass
