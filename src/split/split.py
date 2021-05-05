import ast

from src.descriptors import ClassDescriptor, MethodDescriptor
from src.wrappers import ClassWrapper
from typing import List, Optional, Any, Set, Tuple, Dict, Union
import libcst as cst
import libcst.matchers as m
import importlib
from src.split.split_block import StatementBlock, SplitContext
from dataclasses import dataclass


class RemoveAfterClassDefinition(cst.CSTTransformer):
    def __init__(self, class_name: str):
        self.class_name: str = class_name
        self.is_defined = False

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> Union[cst.BaseStatement, cst.RemovalSentinel]:

        new_decorators = []
        for decorator in updated_node.decorators:
            if "stateflow" not in cst.helpers.get_full_name_for_node(decorator):
                new_decorators.append(decorator)

        if original_node.name == self.class_name:
            self.is_defined = True
            return updated_node.with_changes(decorators=tuple(new_decorators))

        return updated_node.with_changes(decorators=tuple(new_decorators))

    # def on_leave(
    #     self, original_node: cst.CSTNodeT, updated_node: cst.CSTNodeT
    # ) -> Union[cst.CSTNodeT, cst.RemovalSentinel]:
    #     if self.is_defined:
    #         return cst.RemovalSentinel()


class SplitTransformer(cst.CSTTransformer):
    def __init__(
        self, class_name: str, updated_methods: Dict[str, List[StatementBlock]]
    ):
        self.class_name: str = class_name
        self.updated_methods = updated_methods

    def visit_ClassDef(self, node: cst.ClassDef):
        if node.name.value != self.class_name:
            return False
        return True

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> Union[cst.BaseStatement, cst.RemovalSentinel]:
        if updated_node.name.value != self.class_name:
            return updated_node

        class_body = updated_node.body.body

        for method in self.updated_methods.values():
            for split in method:
                class_body = (*class_body, split.new_function)

        return updated_node.with_changes(
            body=updated_node.body.with_changes(body=class_body)
        )

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.CSTNode:
        if (
            m.matches(original_node.body, m.IndentedBlock())
            and updated_node.name.value in self.updated_methods
        ):
            pass_node = cst.SimpleStatementLine(body=[cst.Pass()])
            new_block = original_node.body.with_changes(body=[pass_node])
            return updated_node.with_changes(body=new_block)

        return updated_node


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

        # Unparsed blocks
        self.statements: List[cst.BaseStatement] = []

        # Parsed blocks
        self.current_block_id: int = 0
        self.parsed_statements: List["StatementBlock"] = []

        # Analyze this method.
        self._analyze()

        if len(self.parsed_statements) > 0:
            last_block = self.parsed_statements[-1]
        else:
            last_block = None

        # Parse the 'last' statement.
        self.parsed_statements.append(
            StatementBlock(
                self.current_block_id,
                self.statements,
                SplitContext(
                    self.expression_provider,
                    self.method_node,
                    self.method_desc,
                    previous_block=last_block,
                ),
                last_block=True,
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
        split_block = StatementBlock(
            self.current_block_id,
            self.statements,
            SplitContext(
                self.expression_provider,
                self.method_node,
                self.method_desc,
                previous_block=self.parsed_statements[-1]
                if self.current_block_id > 0
                else None,
            ),
            class_invoked=class_invoked,
            class_call_ref=class_call_ref,
            method_invoked=method,
            call_args=args,
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
