import ast

from src.analysis.ast_utils import extract_types
from src.descriptors import ClassDescriptor, MethodDescriptor
from src.wrappers.class_wrapper import ClassWrapper
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
    Block,
    Def,
)
from src.split.conditional_block import ConditionalBlock, ConditionalBlockContext
from src.split.split_transform import RemoveAfterClassDefinition, SplitTransformer
import re


class HasInteraction(cst.CSTVisitor):
    def __init__(
        self,
        node_to_analyze: cst.CSTNode,
        split_context: SplitContext,
        single: bool = False,
    ):
        self.has_interaction = False
        self.split_context = split_context
        self.invocation_context: Optional[InvocationContext] = None
        self.single: bool = single

        node_to_analyze.visit(self)

    def visit_Call(self, node: cst.Call):
        # Simple case: `item.update_stock()`
        # item is passed as parameter
        if m.matches(node.func, m.Attribute(m.Name(), m.Name())):
            attr: cst.Attribute = node.func

            callee_expr: cst.Expr = attr.value

            callee: str = callee_expr.value
            method: str = attr.attr.value

            # Find callee class in the complete 'context'.
            desc: ClassDescriptor = self.split_context.class_descriptors.get(
                self.split_context.original_method_desc.input_desc[callee]
            )

            if desc is not None:
                if (
                    self.has_interaction and not self.single
                ):  # We do not allow multiple calls on one line.
                    raise AttributeError(
                        "Multiple calls in an if condition are not yet supported. "
                        "You could evaluate the if-conditions in multiple statements "
                        f"_before_ the if-block. The previous call was {self.invocation_context}"
                    )
                else:
                    self.invocation_context = InvocationContext(
                        desc,
                        callee_expr,
                        method,
                        desc.get_method_by_name(method),
                        node.args,
                    )
                    self.has_interaction = True

    def get(self) -> bool:
        return self.has_interaction

    def get_invocation(self) -> Optional[InvocationContext]:
        return self.invocation_context


class SplitAnalyzer(cst.CSTVisitor):
    def __init__(
        self,
        class_node: cst.ClassDef,
        split_context: SplitContext,
        unparsed_statements: List[cst.CSTNode],
        block_id_offset: int = 0,
        outer_block: bool = True,
        annotated_definitions: List[Def] = [],
    ):
        self.class_node: cst.ClassDef = class_node
        self.split_context: SplitContext = split_context
        self.unparsed_statements: List[cst.CSTNode] = [
            stmt
            for stmt in unparsed_statements
            if not m.matches(stmt, m.TrailingWhitespace())
        ]
        self.outer_block: bool = outer_block

        # Unparsed blocks
        self.statements: List[cst.BaseStatement] = []

        # Parsed blocks
        self.current_block_id: int = block_id_offset
        self.block_id_offset = block_id_offset
        self.blocks: List[Block] = []

        # Definitions so far (including those of the parent block).
        self.annotated_definitions: List[Def] = annotated_definitions

        # Keep track if we're currently processing an if-statement.
        self._processing_if: bool = False
        # The body of each if-statement is an unlinked block, which we need to link to the 'latest block'.
        self._unlinked_blocks: List[Block] = []
        self._unlinked_conditional: Optional[ConditionalBlock] = None

        # Analyze this method.
        if self.outer_block:
            self._outer_analyze()
        else:
            self._inner_analyze()

    def _add_block(self, block: Block):
        if (
            not self._processing_if
        ):  # We can only process unlinked blocks, if we're out of the if-statement.
            [b.set_next_block(block) for b in self._unlinked_blocks]

            if self._unlinked_conditional:
                self._unlinked_conditional.set_next_block(block)
                self._unlinked_conditional.set_false_block(block)

            self._unlinked_blocks = []
            self._unlinked_conditional = None
        self.blocks.append(block)

    def _analyze_statements(self):
        for stmt in self.unparsed_statements:
            stmt.visit(self)
            if not (m.matches(stmt, m.If())):
                self.statements.append(stmt)

    def _get_previous_invocation(self) -> Optional[InvocationContext]:
        previous_invocation: Optional[InvocationContext] = None
        if len(self.blocks) > 0 and not isinstance(
            self.blocks[-1].split_context, LastBlockContext
        ):
            previous_invocation = self.blocks[-1].split_context.current_invocation

        return previous_invocation

    def _get_previous_block(self) -> Optional[Block]:
        if (
            len(self.blocks) > 0
            and not self._processing_if
            and not isinstance(self.blocks[-1].split_context, LastBlockContext)
        ):
            return self.blocks[-1]
        return None

    def _inner_analyze(self):
        self._analyze_statements()
        previous_block: Optional[Block] = self._get_previous_block()

        if len(self.statements) > 0 and m.matches(
            self.statements[-1], m.SimpleStatementLine(body=[m.Return()])
        ):
            final_block: Block = StatementBlock(
                self.current_block_id,
                self.statements,
                LastBlockContext.from_instance(
                    self.split_context,
                    previous_invocation=self._get_previous_invocation(),
                ),
                previous_block,
                "block without invocation",
            )
        else:
            final_block: Block = StatementBlock(
                self.current_block_id,
                self.statements,
                IntermediateBlockContext.from_instance(
                    self.split_context,
                    current_invocation=None,
                    previous_invocation=self._get_previous_invocation(),
                ),
                previous_block,
                "block without invocation",
            )
        self._add_block(final_block)

        if previous_block:
            previous_block.set_next_block(final_block)

    def _outer_analyze(self):
        if not m.matches(self.split_context.original_method_node, m.FunctionDef()):
            raise AttributeError(
                f"Expected a function definition but got an {self.split_context.original_method_node}."
            )

        for param in self.split_context.original_method_node.params.params:
            if m.matches(param, m.Param(name=m.Name(), annotation=m.Annotation())):
                name: str = param.name.value
                typ: str = extract_types(
                    self.split_context.class_desc.module_node, param.annotation
                )

                # We see parameters also as declarations.
                self.annotated_definitions.append(Def(name, typ))

        self._analyze_statements()

        previous_block: Optional[Block] = self._get_previous_block()
        final_block: Block = StatementBlock(
            self.current_block_id,
            self.statements,
            LastBlockContext.from_instance(
                self.split_context,
                previous_invocation=self._get_previous_invocation(),
            ),
            previous_block,
            "block without invocation",
        )
        self._add_block(final_block)

        if previous_block:
            previous_block.set_next_block(final_block)

    def need_to_split(self, var: str) -> Tuple[bool, ClassDescriptor]:
        # We walk reversed through all definitions, so we know its the correct order.
        for d in reversed(self.annotated_definitions):
            equal_var: bool = var == d.name
            if (
                d.typ  # If the type exists.
                and equal_var  # If the variable equals the declaration.
            ):
                return self._type_is_class(
                    d.typ
                )  # If the type is another stateful function.
            elif (
                equal_var
            ):  # Above conditions are not all true, but it is still the correct var name.
                return False, None

        return False, None

    def _type_is_class(self, typ: str) -> Tuple[bool, ClassDescriptor]:
        match = re.compile(r"(?<=\[)(.*?)(?=\])").search(typ)

        if not match:
            match = typ
        else:
            match = match.group(0)

        class_desc = self.split_context.class_descriptors.get(match)
        return class_desc is not None, class_desc

    def visit_Call(self, node: cst.Call):
        # Simple case: `item.update_stock()`
        # item is passed as parameter
        if m.matches(node.func, m.Attribute(m.Name(), m.Name())):
            attr: cst.Attribute = node.func

            callee_expr: cst.Expr = attr.value

            callee: str = callee_expr.value
            method: str = attr.attr.value

            need_to_split, desc = self.need_to_split(callee)

            if not need_to_split:
                raise AttributeError(
                    f"We do not need to split, please look into this {callee}.{method}"
                )
                return False

            invocation_context = InvocationContext(
                desc, callee_expr, method, desc.get_method_by_name(method), node.args
            )

            self._process_stmt_block_with_invocation(
                invocation_context, "block with invocation"
            )
        # item_list[i].update_stock()
        elif m.matches(
            node.func,
            m.Attribute(
                m.Subscript(m.Name(), [m.SubscriptElement(m.Index())]), m.Name()
            ),
        ):
            subscript_var: str = node.func.value.value.value
            subscript_code: str = (
                self.split_context.class_desc.module_node.code_for_node(node.func.value)
            )

            method: str = node.func.attr.value
            need_to_split, desc = self.need_to_split(subscript_var)

            if not need_to_split:
                raise AttributeError(
                    f"We do not need to split, please look into this {subscript_code}.{method}"
                )
                return False

            invocation_context = InvocationContext(
                desc,
                node.func.value,
                method,
                desc.get_method_by_name(method),
                node.args,
            )

            self._process_stmt_block_with_invocation(
                invocation_context, "block with invocation"
            )

    def visit_AnnAssign(self, node: cst.AnnAssign):
        if m.matches(node, m.AnnAssign(target=m.Name(), annotation=m.Annotation())):
            typ: str = extract_types(
                self.split_context.class_desc.module_node, node.annotation
            )
            self.annotated_definitions.append(Def(node.target.value, typ))

    def visit_If(self, node: cst.If):
        if len(self.blocks) == 0 or len(self.unparsed_statements) > 0:
            self._process_stmt_block_without_invocation("block before if-statement")

        self._processing_if = True

        # The current if statement, we loop through all nested if nodes.
        current_if: Union[cst.If] = node

        # The current conditional block, initialized to the last.
        conditional_block: Optional[Union[ConditionalBlock, Block]] = self.blocks[-1]

        # The list of the last block of each if body, this needs to be linked up to the next block _after_
        # this if-block.
        last_body_block: List[Block] = []

        # Keep track of the depth of the if-elif statements.
        if_depth: int = 0

        # We keep looping over all (nested) if statements.
        while m.matches(current_if, m.If()):
            # If it has interaction with another stateful function,
            # we first process the arguments of that stateful function and turn it into an InvokeExternal.
            interaction: HasInteraction = HasInteraction(
                current_if.test, self.split_context
            )
            invocation_block: Optional[Block] = None
            if interaction.get():
                self._process_stmt_block_with_invocation(
                    interaction.get_invocation(), "invocation inside (el)if"
                )
                invocation_block = self.blocks[-1]

            # Build the conditional block.
            new_conditional = ConditionalBlock(
                self.current_block_id,
                ConditionalBlockContext.from_instance(
                    self.split_context,
                    previous_invocation=interaction.get_invocation()
                    if interaction.get()
                    else None,
                ),
                current_if.test,
                previous_block=invocation_block,
                invocation_block=invocation_block,
                label="if" if if_depth == 0 else "elif",
            )

            # Connect to conditionals to each other.
            new_conditional.get_start_block().set_previous_block(conditional_block)
            conditional_block.set_next_block(new_conditional.get_start_block())

            if isinstance(conditional_block, ConditionalBlock):
                conditional_block.set_false_block(new_conditional.get_start_block())

            # Add conditional block and update state.
            self._add_block(new_conditional)
            self.current_block_id += 1

            conditional_block = new_conditional

            # Build body of this if_block.
            analyze_if_body: SplitAnalyzer = SplitAnalyzer(
                self.class_node,
                self.split_context,
                current_if.body.children,
                block_id_offset=self.current_block_id,
                outer_block=False,
                annotated_definitions=self.annotated_definitions,
            )

            # These are the blocks inside the if body.
            # Blocks _within_ this list should already be properly linked up.
            if_blocks: List[Block] = analyze_if_body.blocks
            self.annotated_definitions.extend(analyze_if_body.annotated_definitions)

            label = "if body" if if_depth == 0 else "elif body"
            [b.set_label(label) for b in if_blocks]

            # Link up first if_block, to conditional:
            conditional_block.set_next_block(if_blocks[0])
            conditional_block.set_true_block(if_blocks[0])
            if_blocks[0].set_previous_block(conditional_block)

            # We track a list of the latest block of each if-body, so that we can link it up to the block _after_
            # the if statement.
            if not isinstance(if_blocks[-1].split_context, LastBlockContext):
                last_body_block.append(if_blocks[-1])

            # Update outer-scope.
            self.blocks.extend(if_blocks)
            self.current_block_id = self.block_id_offset + len(self.blocks)

            print(f"Just investigated conditional {conditional_block.block_id}")
            print(conditional_block.code())
            print(f"It has the following statements:")
            for stmt in if_blocks:
                print(f"Block: {stmt.block_id}")
                print(stmt.code())

            # Pick next if, else, or None.
            current_if = current_if.orelse
            if_depth += 1

        # If we have an Else clause, we treat it differently.
        if m.matches(current_if, m.Else()):
            else_stmt: cst.Else = current_if
            analyze_else_body: SplitAnalyzer = SplitAnalyzer(
                self.class_node,
                self.split_context,
                else_stmt.body.children,
                block_id_offset=self.current_block_id,
                outer_block=False,
                annotated_definitions=self.annotated_definitions,
            )

            else_blocks: List[StatementBlock] = analyze_else_body.blocks
            self.annotated_definitions.extend(analyze_else_body.annotated_definitions)
            [b.set_label("else body") for b in else_blocks]

            # We connect the first block of this else body, to the last conditional.
            # We assume this conditional_block is not None, because you can't have an "else" clause
            # without an if or elif before it.
            conditional_block.set_next_block(else_blocks[0])
            conditional_block.set_false_block(else_blocks[0])
            else_blocks[0].set_previous_block(conditional_block)

            # We track a list of the latest block of each if-body, so that we can link it up to the block _after_
            # the if statement.
            if not isinstance(if_blocks[-1].split_context, LastBlockContext):
                last_body_block.append(if_blocks[-1])

            # Update outer-scope.
            self.blocks.extend(else_blocks)
            self.current_block_id = self.block_id_offset + len(self.blocks)
        else:
            self._unlinked_conditional = conditional_block

        print(f"Unlinked blocks: {[b.block_id for b in last_body_block]}")
        self._unlinked_blocks = last_body_block
        self._processing_if = False

        return False

    def _process_stmt_block_without_invocation(self, label: str = ""):
        if self.current_block_id == 0:
            split_context = FirstBlockContext.from_instance(
                self.split_context,
                current_invocation=None,
            )
        else:
            split_context = IntermediateBlockContext.from_instance(
                self.split_context,
                previous_invocation=self._get_previous_invocation(),
                current_invocation=None,
            )

        self._process_stmt_block(split_context, label)

    def _process_stmt_block_with_invocation(
        self, invocation_context: InvocationContext, label: str = ""
    ):
        if self.current_block_id == 0:
            split_context = FirstBlockContext.from_instance(
                self.split_context,
                current_invocation=invocation_context,
            )
        else:
            split_context = IntermediateBlockContext.from_instance(
                self.split_context,
                previous_invocation=self._get_previous_invocation(),
                current_invocation=invocation_context,
            )

        self._process_stmt_block(split_context, label)

    def _process_stmt_block(self, split_context: SplitContext, label: str = ""):
        previous_block: Optional[Block] = self._get_previous_block()

        split_block = StatementBlock(
            self.current_block_id,
            self.statements,
            split_context,
            previous_block=previous_block,
            label=label,
        )

        # Set previous block.
        if previous_block:
            previous_block.set_next_block(split_block)

        self._add_block(split_block)

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
                        method.method_node.body.children,
                    )

                    parsed_stmts: List[StatementBlock] = analyzer.blocks
                    updated_methods[method.method_name] = parsed_stmts

                    from src.util import dataflow_visualizer

                    dataflow_visualizer.visualize(blocks=parsed_stmts, code=True)

                    method.split_function(parsed_stmts)

            if len(updated_methods) > 0:
                remove_after_class_def = RemoveAfterClassDefinition(desc.class_name)

                modified_tree = desc.module_node.visit(remove_after_class_def)

                modified_tree = modified_tree.visit(
                    SplitTransformer(desc.class_name, updated_methods)
                )

                # Recompile the code and set the code in the wrapper.
                exec(compile(modified_tree.code, "", mode="exec"), globals(), globals())
                # self.wrappers[i].cls = globals()[desc.class_name]
                self.wrappers[i].cls = modified_tree.code
