import libcst as cst
from src.split.split_block import SplitContext, Use
from typing import List


class ConditionalExpressionAnalyzer(cst.CSTVisitor):
    def __init__(self, expression_provider):
        self.expression_provider = expression_provider
        self.usages: List[Use] = []

    # TODO Verify if we have a Call, we need to add a InvokeExternal before this node + add the result as usage.
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
        test.visit(analyzer)

        self.dependencies: List[str] = [u.name for u in analyzer.usages]
        self.new_function: cst.FunctionDef = self.build_definition()

    def fun_name(self) -> str:
        """Get the name of this function given the block id.
        :return: the (unique) name of this block.
        """
        return (
            f"{self.split_context.original_method_node.name.value}_cond_{self.block_id}"
        )

    def _build_params(self) -> cst.Parameters:
        params: List[cst.Param] = [cst.Param(cst.Name(value="self"))]
        for usage in self.dependencies:
            params.append(cst.Param(cst.Name(value=usage)))
        param_node: cst.Parameters = cst.Parameters(tuple(params))

        return param_node

    def _build_return(self) -> cst.SimpleStatementLine:
        return cst.SimpleStatementLine(body=[cst.Return(self.test_expr)])

    def build_definition(self) -> cst.FunctionDef:
        fun_name: cst.Name = cst.Name(self.fun_name())
        param_node: cst.Paramaters = self._build_params()
        return_node: cst.SimpleStatementLine = self._build_return()

        return self.split_context.original_method_node.with_changes(
            name=fun_name,
            params=param_node,
            body=self.split_context.original_method_node.body.with_changes(
                body=return_node
            ),
        )
