import ast

from src.descriptors import ClassDescriptor, MethodDescriptor
from typing import List, Optional, Any, Set, Tuple, Dict, Union
import libcst as cst
import libcst.matchers as m
import importlib


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
        self, class_name: str, updated_methods: Dict[str, List["StatementBlock"]]
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
                self.expression_provider,
                self.statements,
                self.method_node,
                self.method_desc,
                last_block=last_block,
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

            print(f"{callee}.{method}")
            self._process_stmt_block(desc, method, node.args)

    def _process_stmt_block(
        self, class_invoked: ClassDescriptor, method: str, args: List[cst.Arg]
    ):
        split_block = StatementBlock(
            self.current_block_id,
            self.expression_provider,
            self.statements,
            self.method_node,
            self.method_desc,
            class_invoked=class_invoked,
            method_invoked=method,
            call_args=args,
        )
        self.parsed_statements.append(split_block)

        # Update local state.
        self.statements = []
        self.current_block_id += 1


class StatementBlockAnalyzer(cst.CSTTransformer):
    def __init__(self, expression_provider, method_name: Optional[str] = None):
        self.expression_provider = expression_provider
        self.method_name = method_name

        self.definitions: List[str] = []
        self.usages: List[str] = []

        self.returns = 0

    def visit_Call(self, node: cst.Call):
        if m.matches(node.func, m.Attribute(m.Name(), m.Name())):
            attr: cst.Attribute = node.func
            method: str = attr.attr.value

            # We don't want to visit this node, because it will give LOAD/STORE of unused variables.
            # I.e. we will replace this node later on.
            if method == self.method_name:
                print("I'm here!")
                return False

    def visit_Name(self, node: cst.Name):
        if node in self.expression_provider:
            expression_context = self.expression_provider[node]
            if (
                expression_context == cst.metadata.ExpressionContext.STORE
                and node.value != "self"
            ):
                self.definitions.append(node.value)
            elif (
                expression_context == cst.metadata.ExpressionContext.LOAD
                and node.value != "self"
                and node.value != "True"
                and node.value != "False"
            ):
                self.usages.append(node.value)

    def visit_Return(self, node: cst.Return):
        self.returns += 1


class RemoveCall(cst.CSTTransformer):
    def __init__(self, method_name: str, replace_block: cst.CSTNode):
        self.method_name: str = method_name
        self.replace_block: cst.CSTNode = replace_block

    def leave_Call(
        self, original_node: cst.Call, updated_node: cst.Call
    ) -> cst.BaseExpression:
        if m.matches(original_node.func, m.Attribute(m.Name(), m.Name())):
            attr: cst.Attribute = original_node.func
            method: str = attr.attr.value

            if method == self.method_name:
                return self.replace_block


class StatementBlock:
    def __init__(
        self,
        block_id: int,
        expression_provider,
        statements: List[cst.BaseStatement],
        original_method: cst.FunctionDef,
        method_desc: "MethodDescriptor",
        class_invoked: Optional["ClassDescriptor"] = None,
        method_invoked: Optional[str] = None,
        call_args: Optional[List[cst.Arg]] = None,
        last_block: Optional["StatementBlock"] = None,
    ):
        self.block_id = block_id
        self.last_block = last_block
        self.returns = 0
        self.original_method = original_method
        self.method_desc = method_desc

        self.statements = statements

        self.class_invoked = class_invoked
        self.method_invoked = method_invoked
        self.call_args = call_args

        definitions: List[str] = []
        usages: List[str] = []

        if m.matches(self.statements[0], m.TrailingWhitespace()):
            self.statements.pop(0)

        for statement in self.statements:
            if self.last_block:
                method_invoked = self.last_block.method_invoked
            else:
                method_invoked = None

            stmt_analyzer = StatementBlockAnalyzer(expression_provider, method_invoked)
            statement.visit(stmt_analyzer)

            # Merge usages and definitions
            definitions.extend(stmt_analyzer.definitions)
            usages.extend(stmt_analyzer.usages)

            self.returns += stmt_analyzer.returns

        self.definitions: Set[str] = set(definitions)
        self.usages: Set[str] = set(usages)

        self.new_function: cst.FunctionDef = self.build()

    def _get_invoked_method_descriptor(self) -> "MethodDescriptor":
        return self.class_invoked.get_method_by_name(self.method_invoked)

    def _build_argument_assignments(
        self,
    ) -> List[Tuple[cst.Name, cst.SimpleStatementLine]]:
        assign_list: List[Tuple[cst.Name, cst.SimpleStatementLine]] = []
        for i, arg in enumerate(self.call_args):
            assign_value: cst.BaseExpression = arg.value

            # We name it based on the InputDescriptor of the invoked method.
            if m.matches(arg.keyword, m.Name()):
                assign_name: str = self.method_invoked + "_" + arg.keyword.value
            else:
                assign_name: str = (
                    "invoke_"
                    + self.method_invoked
                    + "_arg_"
                    + self._get_invoked_method_descriptor().input_desc.keys()[i]
                )

            target_name: cst.Name = cst.Name(value=assign_name)
            target: cst.AssignTarget = cst.AssignTarget(target_name)

            if i == 0:
                assign_list.append(
                    (
                        target_name,
                        cst.SimpleStatementLine(
                            body=[cst.Assign([target], value=assign_value)],
                            leading_lines=[
                                cst.EmptyLine(),
                                cst.EmptyLine(
                                    comment=cst.Comment(
                                        f"# Autogenerated assignments for the method call to: {self.method_invoked}."
                                    )
                                ),
                            ],
                        ),
                    )
                )
            else:
                assign_list.append(
                    (
                        target_name,
                        cst.SimpleStatementLine(
                            body=[cst.Assign([target], value=assign_value)]
                        ),
                    )
                )
        return assign_list

    def _build_return(self, call_arguments: List[cst.Name]) -> cst.SimpleStatementLine:
        return_names: List[cst.BaseExpression] = []
        for definition in self.definitions:
            return_names.append(cst.Name(value=definition))

        call_arguments_names: str = ",".join([n.value for n in call_arguments])
        call_expression: cst.BaseExpression = cst.parse_expression(
            f"InvokeMethodRequest('{self.class_invoked.class_name}', '{self.method_invoked}', [{call_arguments_names}])"
        )

        return_names.append(call_expression)

        if len(return_names) == 1:
            return cst.SimpleStatementLine(body=[cst.Return(return_names[0])])
        else:
            return cst.SimpleStatementLine(
                body=[
                    cst.Return(cst.Tuple([cst.Element(name) for name in return_names]))
                ]
            )

    def _build_first_block(self) -> cst.FunctionDef:
        self.definitions = self.definitions.union(self.method_desc.input_desc.keys())

        diff_usages_def = self.usages.difference(self.definitions)
        if (
            len(diff_usages_def) > 0
        ):  # We have usages which are never defined, we should probably throw an error?
            pass

        # Function signature
        fun_name: cst.Name = cst.Name(
            f"{self.original_method.name.value}_{self.block_id}"
        )
        params: cst.Parameters = self.original_method.params

        # Assignments for the call.
        argument_assignments = self._build_argument_assignments()

        # Return statement
        return_stmt: cst.Return = self._build_return(
            [name for name, _ in argument_assignments]
        )

        if m.matches(self.original_method.body, m.IndentedBlock()):
            final_body = (
                self.statements
                + [assign for _, assign in argument_assignments]
                + [return_stmt]
            )

            function_body = self.original_method.body.with_changes(body=final_body)

        else:
            raise AttributeError(
                f"Expected the body of a function to be in an indented block, but got an {self.original_method.body}."
            )

        return self.original_method.with_changes(
            name=fun_name, params=params, body=function_body, returns=None
        )

    def _previous_call_result(self) -> cst.Name:
        return cst.Name(f"{self.last_block.method_invoked}_return")

    def _build_last_block(self) -> cst.FunctionDef:
        # Function signature
        fun_name: cst.Name = cst.Name(
            f"{self.original_method.name.value}_{self.block_id}"
        )

        diff_usages_def = self.usages.difference(self.definitions)

        params: List[cst.Param] = [cst.Param(cst.Name(value="self"))]
        for usage in diff_usages_def:
            params.append(cst.Param(cst.Name(value=usage)))

        previous_block_call: cst.Name = self._previous_call_result()
        params.append(cst.Param(previous_block_call))

        param_node: cst.Parameters() = cst.Parameters(tuple(params))
        returns_signature = self.original_method.returns

        self.statements[0] = self.statements[0].visit(
            RemoveCall(self.last_block.method_invoked, self._previous_call_result())
        )

        if m.matches(self.original_method.body, m.IndentedBlock()):
            final_body = self.statements

            function_body = self.original_method.body.with_changes(
                body=final_body,
            )

        else:
            raise AttributeError(
                f"Expected the body of a function to be in an indented block, but got an {self.original_method.body}."
            )

        return self.original_method.with_changes(
            name=fun_name,
            params=param_node,
            body=function_body,
            returns=returns_signature,
        )

    def build(self) -> cst.FunctionDef:
        # We know this is the 'first' block in the flow.
        # We can simple use the same signature as the original function.
        if self.block_id == 0 and not self.last_block:
            return self._build_first_block()
        elif self.last_block:
            return self._build_last_block()


class InvokeMethodRequest:
    def __init__(self, class_name: str, method_to_invoke: str, args: List[Any]):
        self.class_name = class_name
        self.method_to_invoke = method_to_invoke
        self.args = args


class Split:
    def __init__(self, descriptors: List[ClassDescriptor]):
        self.descriptors = descriptors

    def find_descriptor_by_name(self, class_name: str):
        return [desc for desc in self.descriptors if desc.class_name == class_name][0]

    def split_methods(self):
        for desc in self.descriptors:
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

                    method.split_function(parsed_stmts, self.descriptors)

            if len(updated_methods) > 0:
                remove_after_class_def = RemoveAfterClassDefinition(desc.class_name)

                modified_tree = desc.module_node.visit(remove_after_class_def)

                modified_tree = modified_tree.visit(
                    SplitTransformer(desc.class_name, updated_methods)
                )

                # Recompile the code.
                exec(compile(modified_tree.code, "", mode="exec"), globals(), globals())
                print(globals()[desc.class_name])
