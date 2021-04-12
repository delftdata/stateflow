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

        # Analyze this method.
        self._analyze()

    def _analyze(self):
        if not m.matches(self.method_node, m.FunctionDef()):
            raise AttributeError(
                f"Expected a function definition but got an {self.method_node}."
            )

        for stmt in self.method_node.body.children:
            self.statements.append(stmt)
            stmt.visit(self)

    def visit_Call(self, node: cst.Call):
        # Simple case: `item.update_stock()`
        if m.matches(node.func, m.Attribute(m.Name(), m.Name())):
            attr: cst.Attribute = node.func

            callee: str = attr.value.value
            method: str = attr.attr.value

            print(f"{callee}.{method}")
            self._process_stmt_block()

    def _process_stmt_block(self):
        split_block = SplitStatementBlock(
            self.current_block_id,
            self.expression_provider,
            self.statements,
            self.method_node,
            self.method_desc,
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
        self.returns += 1


class SplitStatementBlock:
    def __init__(
        self,
        block_id: int,
        expression_provider,
        statements: List[cst.BaseStatement],
        original_method: cst.FunctionDef,
        method_desc: MethodDescriptor,
    ):
        self.block_id = block_id
        self.returns = 0
        self.original_method = original_method
        self.method_desc = method_desc

        definitions: List[str] = []
        usages: List[str] = []

        for statement in statements:
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

    def build(self) -> cst.FunctionDef:
        # We know this is the 'first' block in the flow.
        # We can simple use the same signature as the original function.
        if self.block_id == 0:
            self.definitions = self.definitions.union(
                self.method_desc.input_desc.keys()
            )

            diff_usages_def = self.usages.difference(self.definitions)
            if len(
                diff_usages_def
            ):  # We have usages which are never defined, we should probably throw an error?
                pass


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
