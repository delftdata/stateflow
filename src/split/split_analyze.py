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
from src.split.split_transform import RemoveAfterClassDefinition, SplitTransformer
from dataclasses import dataclass


class SplitAnalyzer(cst.CSTVisitor):
    def __init__(
        self,
        split: "Split",
        class_node: cst.ClassDef,
        method_node: cst.FunctionDef,
        method_desc: MethodDescriptor,
        expression_provider,
    ):
        self.split = split
        self.class_node: cst.ClassDef = class_node
        self.method_node: cst.FunctionDef = method_node
        self.method_desc: MethodDescriptor = method_desc
        self.expression_provider = expression_provider

        self.split_context = SplitContext(
            self.expression_provider, self.method_node, self.method_desc
        )

        # Unparsed blocks
        self.statements: List[cst.BaseStatement] = []

        # Parsed blocks
        self.current_block_id: int = 0
        self.parsed_statements: List["StatementBlock"] = []

        # Analyze this method.
        self._analyze()

        # Parse the 'last' statement.
        previous_block = self.parsed_statements[-1]
        self.parsed_statements.append(
            StatementBlock(
                self.current_block_id,
                self.statements,
                LastBlockContext.from_instance(
                    self.split_context,
                    previous_invocation=previous_block.split_context.current_invocation,
                ),
            )
        )

    def _analyze(self):
        if not m.matches(self.method_node, m.FunctionDef()):
            raise AttributeError(
                f"Expected a function definition but got an {self.method_node}."
            )

        for stmt in self.method_node.body.children:
            stmt.visit(self)
            self.statements.append(stmt)

    def visit_Call(self, node: cst.Call):
        # Simple case: `item.update_stock()`
        # item is passed as parameter
        if m.matches(node.func, m.Attribute(m.Name(), m.Name())):
            attr: cst.Attribute = node.func

            callee: str = attr.value.value
            method: str = attr.attr.value

            # Find callee class in the complete 'context'.
            desc: ClassDescriptor = self.split.find_descriptor_by_name(
                self.method_desc.input_desc[callee]
            )

            self._process_stmt_block(desc, callee, method, node.args)

    def _process_stmt_block(
        self,
        class_invoked: ClassDescriptor,
        class_call_ref: str,
        method: str,
        args: List[cst.Arg],
    ):
        print("Now processing statement block!")
        # TODO MOVE UPWARDS A METHOD
        invoked_method_desc = class_invoked.get_method_by_name(method)
        invocation_context = InvocationContext(
            class_invoked, class_call_ref, method, invoked_method_desc, args
        )

        if self.current_block_id == 0:
            split_context = FirstBlockContext.from_instance(
                self.split_context,
                current_invocation=invocation_context,
            )
        else:
            previous_block: Union[
                FirstBlockContext, IntermediateBlockContext
            ] = self.parsed_statements[-1].split_context
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
            self.parsed_statements[-1] if self.current_block_id > 0 else None,
        )
        self.parsed_statements.append(split_block)

        # Update local state.
        self.statements = []
        self.current_block_id += 1


@dataclass
class InvokeMethodRequest:
    """Wrapper class to indicate that we need to invoke an (external) method. This is returned by a method
    which is split. It holds all the information necessary for an invocation.
    """

    class_name: str
    instance_ref_var: str
    method_to_invoke: str
    args: List[Any]


class Split:
    def __init__(
        self, descriptors: List[ClassDescriptor], wrappers: List[ClassWrapper]
    ):
        self.wrappers = wrappers
        self.descriptors = descriptors

    def find_descriptor_by_name(self, class_name: str):
        return [desc for desc in self.descriptors if desc.class_name == class_name][0]

    def split_methods(self):
        for i, desc in enumerate(self.descriptors):
            updated_methods: Dict[str, List[StatementBlock]] = {}
            for method in desc.methods_dec:
                if method.has_links():
                    print(
                        f"{method.method_name} has links to other classes/functions. Now analyzing:"
                    )

                    analyzer: SplitAnalyzer = SplitAnalyzer(
                        self,
                        desc.class_node,
                        method.method_node,
                        method,
                        desc.expression_provider,
                    )

                    parsed_stmts: List[StatementBlock] = analyzer.parsed_statements
                    updated_methods[method.method_name] = parsed_stmts

                    method.split_function(
                        desc.class_name, parsed_stmts, self.descriptors
                    )

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
