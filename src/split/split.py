import ast

from src.descriptors import ClassDescriptor, MethodDescriptor
from typing import List, Dict, Any, Set
import libcst as cst
import libcst.matchers as m


class SplitAnalyzer(cst.CSTVisitor):
    def __init__(
        self,
        class_node: cst.ClassDef,
        method_node: cst.FunctionDef,
        method_desc: MethodDescriptor,
        expression_provider,
    ):
        self.class_node: cst.ClassDef = class_node
        self.method_node: cst.FunctionDef = method_node
        self.method_desc: MethodDescriptor = method_desc
        self.expression_provider = expression_provider

        # Unparsed blocks
        self.statements: List[cst.BaseStatement] = []

        # Parsed blocks
        self.current_block_id: int = 0
        self.parsed_statements: List["SplitStatementBlock"] = []

    def visit_FunctionDef(self, node: cst.FunctionDef):
        print(f"HERE {node.name}")

    def visit_Call(self, node: cst.Call):
        # Simple case: `item.update_stock()`
        if m.matches(node.func, m.Attribute(m.Name(), m.Name())):
            attr: cst.Attribute = node.func

            callee: str = attr.value.value
            method: str = attr.attr.value

            print(f"{callee}.{method}")
            self._process_stmt_block()

    def visit_SimpleStatementLine(self, node: cst.SimpleStatementLine):
        self.statements.append(node)

    def visit_SimpleStatementSuite(self, node: "SimpleStatementSuite"):
        print(f"HM { node}")

    def visit_If(self, node: cst.If):
        self.statements.append(node)

    def visit_For(self, node: cst.For):
        self.statements.append(node)

    def visit_While(self, node: cst.While):
        self.statements.append(node)

    def visit_Try(self, node: cst.Try):
        self.statements.append(node)

    def visit_With(self, node: cst.With):
        self.statements.append(node)

    def _process_stmt_block(self):
        split_block = SplitStatementBlock(
            self.current_block_id, self.expression_provider, self.statements
        )
        self.parsed_statements.append(split_block)

        # Update local state.
        self.statements = []
        self.current_block_id += 1


class StatementBlockAnalyzer(cst.CSTVisitor):
    def __init__(self, expression_provider):
        self.expression_provider = expression_provider

        self.definitions: List[str] = []
        self.usages: List[str] = []

        self.returns = 0

    def visit_Name(self, node: cst.Name):
        if node in self.expression_provider:
            expression_context = self.expression_provider[node]
            if (
                expression_context == cst.metadata.ExpressionContext.STORE
                and node.value != "self"
            ):
                self.definitions.append(node.value)
            elif (
                expression_context == cst.metadata.ExpressionContext.LOAD
                and node.value != "self"
                and node.value != ("True" and "False")
            ):
                self.usages.append(node.value)

    def visit_Return(self, node: cst.Return):
        print(node)
        self.returns += 1


class SplitStatementBlock:
    def __init__(
        self,
        block_id: int,
        expression_provider,
        statements: List[cst.BaseStatement],
    ):
        self.block_id = block_id
        self.returns = 0

        definitions: List[str] = []
        usages: List[str] = []

        # print(len(statements))
        for statement in statements:
            # print(f"Now visiting {statement}")
            stmt_analyzer = StatementBlockAnalyzer(expression_provider)
            statement.visit(stmt_analyzer)

            # Merge usages and definitions
            definitions.extend(stmt_analyzer.definitions)
            usages.extend(stmt_analyzer.usages)

            self.returns += stmt_analyzer.returns

        self.definitions: Set[str] = set(definitions)
        self.usages: Set[str] = set(usages)
        print(f"Definitions {set(self.definitions)}")
        print(f"Usages {set(self.usages)}")
        print(f"Amount of returns in this block {self.returns}")


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

                    analyzer = SplitAnalyzer(
                        desc.class_node,
                        method.method_node,
                        method,
                        desc.expression_provider,
                    )
                    method.method_node.visit(analyzer)
