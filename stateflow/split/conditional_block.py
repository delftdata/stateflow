import libcst as cst
from libcst import matchers as m
from stateflow.split.split_block import (
    SplitContext,
    Use,
    Block,
    StatementBlock,
    InvocationContext,
    ReplaceCall,
    EventFlowNode,
)
from stateflow.dataflow.event_flow import InvokeConditional
from typing import List, Optional, Tuple
from stateflow.descriptors.class_descriptor import ClassDescriptor
from dataclasses import dataclass


@dataclass
class ConditionalBlockContext(SplitContext):
    """This is the context for a conditional block.

    This block may or may not have a previous_invocation.
        If that is the case, we will add it as parameter and replace the call.
    """

    previous_invocation: Optional[InvocationContext] = None


class ConditionalExpressionAnalyzer(cst.CSTVisitor):
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


class ConditionalBlock(Block):
    def __init__(
        self,
        block_id: int,
        split_context: ConditionalBlockContext,
        test: cst.BaseExpression,
        previous_block: Optional[Block] = None,
        invocation_block: Optional[Block] = None,
        label: str = "",
        state_request: List[Tuple[str, ClassDescriptor]] = [],
    ):
        super().__init__(block_id, split_context, previous_block, label, state_request)
        self.test_expr: cst.BaseExpression = test
        self.invocation_block: Optional[Block] = invocation_block

        if self.invocation_block:
            self.invocation_block.set_next_block(self)

        # Get rid of the invocation and replace with the result.
        if self.split_context.previous_invocation:
            self.test_expr = self.test_expr.visit(
                ReplaceCall(
                    self.split_context.previous_invocation.method_invoked,
                    self._previous_call_result(),
                )
            )

        # Verify usages of this block.
        analyzer: ConditionalExpressionAnalyzer = ConditionalExpressionAnalyzer(
            split_context.expression_provider
        )
        self.test_expr.visit(analyzer)

        self.true_block: Optional[Block] = None
        self.false_block: Optional[Block] = None

        self.dependencies: List[str] = [u.name for u in analyzer.usages]
        self.new_function: cst.FunctionDef = self.build_definition()

    def fun_name(self) -> str:
        """Get the name of this function given the block id.
        :return: the (unique) name of this block.
        """
        return (
            f"{self.split_context.original_method_node.name.value}_cond_{self.block_id}"
        )

    def _get_true_block(self) -> Optional[Block]:
        return self.true_block

    def _get_false_block(self) -> Optional[Block]:
        return self.false_block

    def set_true_block(self, block: Block):
        self.true_block = block

    def set_false_block(self, block: Block):
        self.false_block = block

    def get_start_block(self) -> Block:
        return self if not self.invocation_block else self.invocation_block

    def _build_return(self) -> cst.SimpleStatementLine:
        return cst.SimpleStatementLine(body=[cst.Return(self.test_expr)])

    def build_event_flow_nodes(self, node_id: int) -> List[EventFlowNode]:
        nodes_block = super().build_event_flow_nodes(node_id)

        # Initialize id.
        flow_node_id = node_id + len(nodes_block) + 1  # Offset the id.

        latest_node: Optional[EventFlowNode] = (
            None if len(nodes_block) == 0 else nodes_block[-1]
        )

        # For re-use purposes, we define the FunctionType of the class this StatementBlock belongs to.
        class_type = self.split_context.class_desc.to_function_type().to_address()

        """ For an conditional node, we assume the following scenario:
            1. We assume that if the conditional relies on an external function,
            the previous node has that result. 
            2. The conditional is simply evaluated and based on the result,
            the path is decided. 
        """
        invoke_conditional: InvokeConditional = InvokeConditional(
            class_type,
            flow_node_id,
            self.fun_name(),
            self.dependencies,
            if_true_block_id=self.true_block.block_id,
            if_false_block_id=self.false_block.block_id,
        )

        if latest_node:
            latest_node.set_next(invoke_conditional.id)
            invoke_conditional.set_previous(latest_node.id)

        # The 'true' and 'false' block are updated later on.
        # We don't know their id's yet.

        return nodes_block + [invoke_conditional]

    def build_definition(self) -> cst.FunctionDef:
        fun_name: cst.Name = cst.Name(self.fun_name())
        param_node: cst.Paramaters = self._build_params()

        return_node: cst.SimpleStatementLine = self._build_return()
        return self.split_context.original_method_node.with_changes(
            name=fun_name,
            params=param_node,
            body=self.split_context.original_method_node.body.with_changes(
                body=[return_node]
            ),
        )
