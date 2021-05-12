import ast

from src.descriptors import ClassDescriptor, MethodDescriptor
from src.wrappers import ClassWrapper
from typing import List, Optional, Any, Set, Tuple, Dict, Union
import libcst as cst
import libcst.matchers as m
import importlib
from src.split.split_block import (
    StatementBlock,
    SplitContext,
    FirstBlockContext,
    LastBlockContext,
    IntermediateBlockContext,
    InvocationContext,
)
from src.split.conditional_block import ConditionalBlock
from src.split.split_transform import RemoveAfterClassDefinition, SplitTransformer
from src.dataflow.event_flow import InvokeMethodRequest


class HasInteraction(cst.CSTVisitor):
    def __init__(self, node_to_analyze: cst.CSTNode, split_context: SplitContext):
        self.has_interaction = False
        self.split_context = split_context

        node_to_analyze.visit(self)

    def visit_Call(self, node: cst.Call):
        # Simple case: `item.update_stock()`
        # item is passed as parameter
        if m.matches(node.func, m.Attribute(m.Name(), m.Name())):
            attr: cst.Attribute = node.func

            callee: str = attr.value.value

            # Find callee class in the complete 'context'.
            desc: ClassDescriptor = self.split_context.class_descriptors.get(
                self.split_context.original_method_desc.input_desc[callee]
            )

            if desc is not None:
                self.has_interaction = True

    def get(self):
        return self.has_interaction


class SplitAnalyzer(cst.CSTVisitor):
    def __init__(
        self,
        class_node: cst.ClassDef,
        split_context: SplitContext,
        block_id_offset: int = 0,
        outer_block: bool = True,
    ):
        self.class_node: cst.ClassDef = class_node
        self.split_context = split_context

        # Unparsed blocks
        self.statements: List[cst.BaseStatement] = []

        # Parsed blocks
        self.current_block_id: int = block_id_offset
        self.blocks: List["StatementBlock"] = []

        # Analyze this method.
        if outer_block:
            self._outer_analyze()

    def _outer_analyze(self):
        if not m.matches(self.split_context.original_method_node, m.FunctionDef()):
            raise AttributeError(
                f"Expected a function definition but got an {self.split_context.original_method_node}."
            )

        for stmt in self.split_context.original_method_node.body.children:
            stmt.visit(self)
            self.statements.append(stmt)

        # Parse the 'last' statement.
        previous_block = self.blocks[-1]
        self.blocks.append(
            StatementBlock(
                self.current_block_id,
                self.statements,
                LastBlockContext.from_instance(
                    self.split_context,
                    previous_invocation=previous_block.split_context.current_invocation,
                ),
            )
        )

    def visit_Call(self, node: cst.Call):
        # Simple case: `item.update_stock()`
        # item is passed as parameter
        if m.matches(node.func, m.Attribute(m.Name(), m.Name())):
            attr: cst.Attribute = node.func

            callee: str = attr.value.value
            method: str = attr.attr.value

            # Find callee class in the complete 'context'.
            desc: ClassDescriptor = self.split_context.class_descriptors[
                self.split_context.original_method_desc.input_desc[callee]
            ]

            invocation_context = InvocationContext(
                desc, callee, method, desc.get_method_by_name(method), node.args
            )

            self._process_stmt_block(invocation_context)

    def visit_If(self, node: cst.If):
        if not HasInteraction(node, self.split_context).get():
            print("We don't need to identify this block.")
            return False
        else:
            # 1 Build conditional block:
            current_if: cst.If = node
            conditional_block: ConditionalBlock = ConditionalBlock(
                self.current_block_id, self.split_context, node.test
            )

            self.current_block_id += 1

            current_if: cst.If = node
            analyze_if_body: SplitAnalyzer = SplitAnalyzer(
                self.class_node,
                self.split_context,
                block_id_offset=self.current_block_id,
                outer_block=False,
            )
            if_blocks: List[StatementBlock] = analyze_if_body.blocks

        return False

    def _process_stmt_block(self, invocation_context: InvocationContext):
        if self.current_block_id == 0:
            split_context = FirstBlockContext.from_instance(
                self.split_context,
                current_invocation=invocation_context,
            )
        else:
            previous_block: Union[
                FirstBlockContext, IntermediateBlockContext
            ] = self.blocks[-1].split_context
            previous_invocation = previous_block.current_invocation
            split_context = IntermediateBlockContext.from_instance(
                self.split_context,
                previous_invocation=previous_invocation,
                current_invocation=invocation_context,
            )

        split_block = StatementBlock(
            self.current_block_id,
            self.statements,
            split_context,
            self.blocks[-1] if self.current_block_id > 0 else None,
        )
        self.blocks.append(split_block)

        # Update local state.
        self.statements = []
        self.current_block_id += 1


class Split:
    def __init__(
        self, descriptors: List[ClassDescriptor], wrappers: List[ClassWrapper]
    ):
        self.wrappers = wrappers
        self.descriptors = descriptors
        self.name_to_descriptor = {desc.class_name: desc for desc in self.descriptors}

    def split_methods(self):
        for i, desc in enumerate(self.descriptors):
            updated_methods: Dict[str, List[StatementBlock]] = {}
            for method in desc.methods_dec:
                if method.has_links():
                    print(
                        f"{method.method_name} has links to other classes/functions. Now analyzing:"
                    )

                    analyzer: SplitAnalyzer = SplitAnalyzer(
                        desc.class_node,
                        SplitContext(
                            self.name_to_descriptor,
                            desc.expression_provider,
                            method.method_node,
                            method,
                            desc,
                        ),
                    )

                    parsed_stmts: List[StatementBlock] = analyzer.blocks
                    updated_methods[method.method_name] = parsed_stmts

                    method.split_function(parsed_stmts)

            if len(updated_methods) > 0:
                remove_after_class_def = RemoveAfterClassDefinition(desc.class_name)

                modified_tree = desc.module_node.visit(remove_after_class_def)

                modified_tree = modified_tree.visit(
                    SplitTransformer(desc.class_name, updated_methods)
                )

                print(modified_tree.code)

                # Recompile the code and set the code in the wrapper.
                exec(compile(modified_tree.code, "", mode="exec"), globals(), globals())
                self.wrappers[i].cls = globals()[desc.class_name]
