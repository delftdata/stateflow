import libcst as cst
from typing import List, Optional, Set, Tuple, Union
from src.descriptors.method_descriptor import MethodDescriptor
from src.descriptors.class_descriptor import ClassDescriptor
import libcst.matchers as m
from dataclasses import dataclass


@dataclass
class Def:
    name: str


@dataclass
class Use:
    name: str


class StatementAnalyzer(cst.CSTVisitor):
    def __init__(self, expression_provider, method_name: Optional[str] = None):
        self.expression_provider = expression_provider
        self.method_name = method_name

        self.in_assign: bool = False
        self.assign_names: List[Def] = []
        self.def_use: List[Union[Def, Use]] = []

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
                return False

    def _visit_assignment(self):
        if self.in_assign:
            raise AttributeError("A nested assignment?! Should not be possible.")
        self.in_assign = True

    def _leave_assignment(self):
        self.in_assign = False
        self.def_use.extend(self.assign_names)

        self.assign_names = []

    def visit_Assign(self, node: cst.Assign):
        self._visit_assignment()

    def visit_AugAssign(self, node: cst.AugAssign):
        self._visit_assignment()

    def visit_AnnAssign(self, node: cst.AugAssign):
        self._visit_assignment()

    def leave_Assign(self, node: cst.Assign):
        self._leave_assignment()

    def leave_AugAssign(self, node: cst.AugAssign):
        self._leave_assignment()

    def leave_AnnAssign(self, node: cst.AnnAssign):
        self._leave_assignment()

    def leave_Name(self, node: cst.Name):
        if node in self.expression_provider:
            expression_context = self.expression_provider[node]
            if (
                expression_context == cst.metadata.ExpressionContext.STORE
                and node.value != "self"
            ):
                if not self.in_assign:
                    self.def_use.append(Def(node.value))
                else:
                    self.assign_names.append(Def(node.value))

                self.definitions.append(node.value)
            elif (
                expression_context == cst.metadata.ExpressionContext.LOAD
                and node.value != "self"
                and node.value != "True"
                and node.value != "False"
            ):
                self.def_use.append(Use(node.value))
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
        class_call_ref: Optional[str] = None,
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
        self.class_call_ref = class_call_ref
        self.call_args = call_args

        self.arguments_for_call = []

        definitions: List[str] = []
        usages: List[str] = []
        def_use: List[List[Union[Def, Use]]] = []

        if m.matches(self.statements[0], m.TrailingWhitespace()):
            self.statements.pop(0)

        for statement in self.statements:
            if self.last_block:
                method_invoked = self.last_block.method_invoked
            else:
                method_invoked = None

            stmt_analyzer = StatementAnalyzer(expression_provider, method_invoked)
            statement.visit(stmt_analyzer)

            # Merge usages and definitions
            definitions.extend(stmt_analyzer.definitions)
            usages.extend(stmt_analyzer.usages)

            def_use.append(stmt_analyzer.def_use)

            self.returns += stmt_analyzer.returns

        self.dependencies: List[str] = self._compute_dependencies(def_use)
        self.definitions: List[str] = self._compute_definitions(def_use)

        print(self.definitions)

        self.new_function: cst.FunctionDef = self.build()

    def _compute_definitions(
        self, def_use_list: List[List[Union[Def, Use]]]
    ) -> List[str]:
        definitions = []
        for def_use in def_use_list:
            for el in def_use:
                if isinstance(el, Def) and el.name not in definitions:
                    definitions.append(el.name)

        return definitions

    def _compute_dependencies(
        self, def_use_list: List[List[Union[Def, Use]]]
    ) -> List[str]:
        """This method computes the dependencies of this statement block.

        It iterates through all declarations and usages of variables.
        When we see a usage of a variable that has _not_ been declared before, we consider it a dependency.

        For example:
        a = 3
        b = c + 1 + a + b

        returns [c, b]

        :param def_use_list: a list of definitions and usages per statement (we assume it is in the correct order).
        :return: the dependencies of this statement block.
        """
        declarations_so_far = set()
        dependencies = []
        for def_use in def_use_list:
            for el in def_use:
                if isinstance(el, Def):
                    declarations_so_far.add(el.name)
                elif (
                    isinstance(el, Use)
                    and el.name not in declarations_so_far
                    and el.name not in dependencies
                ):
                    dependencies.append(el.name)
        return dependencies

    def _get_invoked_method_descriptor(self) -> "MethodDescriptor":
        return self.class_invoked.get_method_by_name(self.method_invoked)

    def fun_name(self) -> str:
        return f"{self.original_method.name.value}_{self.block_id}"

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

    def get_call_arguments(self) -> List[str]:
        return ",".join([n.value for n in self.arguments_for_call])

    def _build_return(self, call_arguments: List[cst.Name]) -> cst.SimpleStatementLine:
        return_names: List[cst.BaseExpression] = []
        for definition in sorted(self.definitions):
            return_names.append(cst.Name(value=definition))

        call_arguments_names: str = ",".join([n.value for n in call_arguments])
        call_expression: cst.BaseExpression = cst.parse_expression(
            f"InvokeMethodRequest('{self.class_invoked.class_name}', {self.class_call_ref}, '{self.method_invoked}', [{call_arguments_names}])"
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
        self.definitions.extend(list(self.method_desc.input_desc.keys()))

        # Function signature
        fun_name: cst.Name = cst.Name(
            f"{self.original_method.name.value}_{self.block_id}"
        )
        params: cst.Parameters = self.original_method.params

        # Assignments for the call.
        argument_assignments = self._build_argument_assignments()

        self.arguments_for_call = [name for name, _ in argument_assignments]

        # Return statement
        return_stmt: cst.Return = self._build_return(self.arguments_for_call)

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

        params: List[cst.Param] = [cst.Param(cst.Name(value="self"))]
        for usage in self.dependencies:
            params.append(cst.Param(cst.Name(value=usage)))

        previous_block_call: cst.Name = self._previous_call_result()
        params.append(cst.Param(previous_block_call))

        # TODO Hacky, fix it.
        self.dependencies.append(self._previous_call_result().value)

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
