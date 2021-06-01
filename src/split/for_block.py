from src.split.split_block import (
    SplitContext,
    Use,
    Block,
    StatementBlock,
    InvocationContext,
    ReplaceCall,
    EventFlowNode,
)
import libcst as cst
from typing import Optional, List


class ForExpressionAnalyzer(cst.CSTVisitor):
    def __init__(self, expression_provider):
        self.expression_provider = expression_provider
        self.usages: List[Use] = []

    def visit_Name(self, node: cst.Name):
        if node in self.expression_provider:
            expression_context = self.expression_provider[node]

            if (
                expression_context == cst.metadata.ExpressionContext.LOAD
                and node.value != "self"
                and node.value != "True"
                and node.value != "False"
                and node.value != "print"
            ):
                self.usages.append(Use(node.value))


class ForBlock(Block):
    def __init__(
        self,
        block_id: int,
        iter_name: str,
        target: cst.BaseAssignTargetExpression,
        split_context: SplitContext,
        previous_block: Optional[Block] = None,
        label: str = "",
    ):
        super().__init__(block_id, split_context, previous_block, label)
        self.iter_name: str = iter_name
        self.target: str = target
