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


class ForBlock(Block):
    def __init__(
        self,
        block_id: int,
        iter_name: str,
        target: cst.BaseAssignTargetExpression,
        split_context: SplitContext,
        else_block: Optional[Block] = None,
        previous_block: Optional[Block] = None,
        label: str = "",
    ):
        super().__init__(block_id, split_context, previous_block, label)
        self.iter_name: str = iter_name
        self.target: str = target
        self.else_block: Optional[Block] = else_block

        self.dependencies.append(self.iter_name)
        self.new_function: cst.FunctionDef = self.build_definition()

    def set_else_block(self, block: Block):
        self.else_block = block

    def fun_name(self) -> str:
        """Get the name of this function given the block id.
        :return: the (unique) name of this block.
        """
        return (
            f"{self.split_context.original_method_node.name.value}_iter_{self.block_id}"
        )

    def _build_params(self) -> cst.Parameters:
        params: List[cst.Param] = [cst.Param(cst.Name(value="self"))]
        for usage in self.dependencies:
            params.append(cst.Param(cst.Name(value=usage)))

        param_node: cst.Parameters = cst.Parameters(tuple(params))

        return param_node

    def _build_body(self):
        return cst.helpers.parse_template_module(
            """
try:
    {iter_target} = next({it})
except StopIteration:
    return {iter_target}
""",
            iter_target=self.target,
            it=cst.Name(self.iter_name),
        ).body

    def _build_return(self) -> cst.SimpleStatementLine:
        return cst.SimpleStatementLine(
            body=[
                cst.Return(
                    cst.Tuple(
                        [
                            cst.Element(self.target),
                            cst.Element(cst.Name(self.iter_name)),
                        ]
                    )
                )
            ]
        )

    def build_definition(self) -> cst.FunctionDef:
        fun_name: cst.Name = cst.Name(self.fun_name())
        param_node: cst.Paramaters = self._build_params()
        body = self._build_body()
        return_node: cst.SimpleStatementLine = self._build_return()

        return self.split_context.original_method_node.with_changes(
            name=fun_name,
            params=param_node,
            body=self.split_context.original_method_node.body.with_changes(
                body=list(body) + [return_node]
            ),
        )
