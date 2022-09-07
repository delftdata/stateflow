from stateflow.split.split_block import (
    SplitContext,
    Block,
    EventFlowNode,
    ClassDescriptor,
)
from stateflow.dataflow.event_flow import InvokeFor
import libcst as cst
import libcst.matchers as m
from typing import Optional, List, Tuple


class ForBlock(Block):
    def __init__(
        self,
        block_id: int,
        iter_name: str,
        target: cst.BaseAssignTargetExpression,
        split_context: SplitContext,
        previous_block: Optional[Block] = None,
        label: str = "",
        state_request: List[Tuple[str, ClassDescriptor]] = [],
    ):
        super().__init__(block_id, split_context, previous_block, label, state_request)
        self.iter_name: str = iter_name
        self.target: cst.BaseAssignTargetExpression = target
        self.else_block: Optional[Block] = None
        self.body_start_block: Optional[Block] = None

        self.dependencies.append(self.iter_name)
        self.new_function: cst.FunctionDef = self.build_definition()

    def _get_target_name(self):
        if isinstance(self.target, str):
            return self.target
        elif m.matches(self.target, m.Name()):
            return self.target.value
        else:
            raise AttributeError(f"Cannot convert target node to string {self.target}.")

    def set_else_block(self, block: Block):
        self.else_block = block

    def set_body_start_block(self, block: Block):
        self.body_start_block = block

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
    return {'_type': 'StopIteration'}
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

    def build_event_flow_nodes(self, node_id: int):
        # We can only have an else block, a for body block and a next statement block.
        assert len(self.next_block) <= 3

        nodes_block = super().build_event_flow_nodes(node_id)

        latest_node: Optional[EventFlowNode] = (
            None if len(nodes_block) == 0 else nodes_block[-1]
        )

        # Initialize id.
        flow_node_id = node_id + len(nodes_block) + 1  # Offset the id.

        # For re-use purposes, we define the FunctionType of the class this StatementBlock belongs to.
        class_type = self.split_context.class_desc.to_function_type().to_address()

        invoke_for: InvokeFor = InvokeFor(
            class_type,
            flow_node_id,
            self.fun_name(),
            self.iter_name,
            self._get_target_name(),
            for_body_block_id=self.body_start_block.block_id,
            else_block_id=self.else_block.block_id
            if self.else_block is not None
            else -1,
        )

        if latest_node:
            latest_node.set_next(invoke_for.id)
            invoke_for.set_previous(latest_node.id)

        return nodes_block + [invoke_for]

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
