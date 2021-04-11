import ast

from src.descriptors import ClassDescriptor, MethodDescriptor
from typing import List, Dict, Any
import libcst as cst
import libcst.matchers as m


class SplitAnalyzer(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (cst.metadata.ExpressionContextProvider,)

    def __init__(
        self,
        class_node: cst.ClassDef,
        method_node: cst.FunctionDef,
        method_desc: MethodDescriptor,
    ):
        self.class_node: cst.ClassDef = class_node
        self.method_node: cst.FunctionDef = method_node
        self.method_desc: MethodDescriptor = method_desc

        self.declarations: Dict[str, Any] = self.method_desc.method_node

        self.statements = []

    def visit_Call(self, node: cst.Call):
        # Simple case: `item.update_stock()`
        if m.matches(node.func, m.Attribute(m.Name(), m.Name())):
            attr: cst.Attribute = node.func

            callee: str = attr.value.value
            method: str = attr.attr.value

            print(f"{callee}.{method}")

    def leave_SimpleStatementLine(self, node: cst.SimpleStatementLine):
        self.statements.append(node)

    def _process_stmt_block(self):
        SplitStatementBlock(self.statements)
        self.statements = []


class StatementAnalyzer(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (cst.metadata.ExpressionContextProvider,)

    def __init__(self):
        definitions: Dict[str, Any] = {}
        usages: List[str] = []

    def visit_Name(self, node: cst.Name):
        hi = self.get_metadata(cst.metadata.ExpressionContextProvider, node)
        print(hi)


class SplitStatementBlock:
    def __init__(self, statements: List[cst.SimpleStatementLine]):
        self.statements = statements

        definitions: Dict[str, Any] = {}
        usages: List[str] = []

        for statement in statements:
            stmt_analyzer = StatementAnalyzer()
            cst.metadata.MetadataWrapper(statement).visit(stmt_analyzer)

            # Merge usages and definitions


class Split:
    def __init__(self, descriptors: List[ClassDescriptor]):
        self.descriptors = descriptors

    def split_methods(self):
        for desc in self.descriptors:
            for method in desc.methods_dec:
                if method.has_links():
                    print(
                        f"{method.method_name} has links to other classes/functions. Now analyzing:"
                    )

                analyzer = SplitAnalyzer(desc.class_node, method.method_node, method)
                method.method_node.visit(analyzer)
