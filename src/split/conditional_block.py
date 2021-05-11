import libcst as cst
from src.split.split_block import SplitContext, Use
from typing import List


class ConditionalExpressionAnalyzer(cst.CSTVisitor):
    def __init__(self, expression_provider):
        self.expression_provider = expression_provider
        self.usages: List[Use] = []

    # TODO Verify if we have a Call, we need to add a InvokeExternal before this node.
    def visit_Call(self, node: cst.Call):
        pass

    def visit_Name(self, node: cst.Name):
        if node in self.expression_provider:
            expression_context = self.expression_provider[node]

            if expression_context == cst.metadata.ExpressionContext.LOAD:
                self.usages.append(Use(node.value))


class ConditionalBlock:
    def __init__(
        self, block_id: int, split_context: SplitContext, test: cst.BaseExpression
    ):
        self.block_id: int = block_id
        self.split_context: SplitContext = split_context
        self.test_expr: cst.BaseExpression = test

        # Verify usages of this block.
        analyzer: ConditionalExpressionAnalyzer = ConditionalExpressionAnalyzer(
            split_context.expression_provider
        )
        analyzer.visit(test)
        self.dependencies: List[str] = [u.name for u in analyzer.usages]

        self.new_function: cst.FunctionDef = self.build_definition()

    def build_definition(self) -> cst.FunctionDef:
        # build_name
        # set return signature bool
        # set return node with the test_expression.
        pass
