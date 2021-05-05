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
    """Analyzes a statement identifying:
    1. all definitions and usages
    2. the amount of returns.

    """

    def __init__(self, expression_provider, method_name: Optional[str] = None):
        """Initializes a statement analyzer.

        You can pass a method_name to the constructor. The `Call` with this method name will be ignored.
        We need to ignore this method, because it will be removed from the code at some point (if it is a
        spitting point). For example:

        a = item.buy(x), should return [Def(a)]
            but without ignoring this method it will return [Use(item), Use(x), Def(a)].

        :param expression_provider: the expression provider of this node, to provide LOAD and STORE context.
        :param method_name: a method that is called in this statement. We want to ignore that statement.
        """
        self.expression_provider = expression_provider
        self.method_name = method_name

        self.in_assign: bool = False
        self.assign_names: List[Def] = []
        self.def_use: List[Union[Def, Use]] = []

        self.returns = 0

    def visit_Call(self, node: cst.Call):
        """Visits a Call node and ignore if it has the name == self.method_name.

        This will be the 'split' call and therefore definitions/usages in this call need to be ignored.

        :param node: the call node.
        :return: False if it is the split call (children won't be visited then).
        """
        if m.matches(node.func, m.Attribute(m.Name(), m.Name())):
            attr: cst.Attribute = node.func
            method: str = attr.attr.value

            # We don't want to visit this node, because it will give LOAD/STORE of unused variables.
            # I.e. we will replace this node later on.
            if method == self.method_name:
                return False

    def _visit_assignment(self):
        """We keep track of which assignments we visit, so that we can put definitions and usages in the correct order.
        I.e.
        a = x + b, needs to be analyzed as [Use(x), Use(b), Def(a)]. However, LibCST evaluates in the order of
        the declared syntax. As a workaround, we set a flag whenever we visit an assignment. This prevents declarations
        to be added to the list _until_ we leave the assignment node.

        """
        if self.in_assign:
            raise AttributeError("A nested assignment?! Should not be possible.")
        self.in_assign = True

    def _leave_assignment(self):
        """Add names of definitions to the list of use/def variables. Disable the flag and reset the state.
        Also see self._visit__visit_assignment()
        """
        self.in_assign = False
        self.def_use.extend(self.assign_names)

        self.assign_names = []

    def visit_Assign(self, node: cst.Assign):
        """Visits an assignment.

        :param node: the assignment node.
        """
        self._visit_assignment()

    def visit_AugAssign(self, node: cst.AugAssign):
        """Visits an assignment.

        :param node: the assignment node.
        """
        self._visit_assignment()

    def visit_AnnAssign(self, node: cst.AugAssign):
        """Visits an assignment.

        :param node: the assignment node.
        """
        self._visit_assignment()

    def leave_Assign(self, node: cst.Assign):
        """Leaves an assignment.

        :param node: the assignment node.
        """
        self._leave_assignment()

    def leave_AugAssign(self, node: cst.AugAssign):
        """Leaves an assignment.

        :param node: the assignment node.
        """
        self._leave_assignment()

    def leave_AnnAssign(self, node: cst.AnnAssign):
        """Leaves an assignment.

        :param node: the assignment node.
        """
        self._leave_assignment()

    def visit_Name(self, node: cst.Name):
        """Visits a name node.
        Examines if it is a definitions (STORE) or usage (LOAD).
        `self` attributes are ignored.

        :param node: the name node.
        """
        if node in self.expression_provider:
            expression_context = self.expression_provider[node]
            if (
                expression_context == cst.metadata.ExpressionContext.STORE
                and node.value != "self"
            ):
                if not self.in_assign:
                    self.def_use.append(Def(node.value))
                else:
                    # We add definitions only _after_ we left the assignment. Therefore we track it in a separate list.
                    self.assign_names.append(Def(node.value))
            elif (
                expression_context == cst.metadata.ExpressionContext.LOAD
                and node.value != "self"
                and node.value != "True"
                and node.value != "False"
            ):
                self.def_use.append(Use(node.value))

    def visit_Return(self, node: cst.Return):
        """
        Keep track of all returns.
        """
        self.returns += 1


class ReplaceCall(cst.CSTTransformer):
    """Replaces a call with the return result of that call."""

    def __init__(self, method_name: str, replace_node: cst.CSTNode):
        """Initializes a ReplaceCall transformer.

        :param method_name: the method name to replace.
        :param replace_node: the replacement node.
        """
        self.method_name: str = method_name
        self.replace_node: cst.CSTNode = replace_node

    def leave_Call(
        self, original_node: cst.Call, updated_node: cst.Call
    ) -> cst.BaseExpression:
        """We replace a return Call with the return result of that call.

        :param original_node: the original node call.
        :param updated_node: the return result node.
        :return: an updated node if neccessary.
        """

        if m.matches(original_node.func, m.Attribute(m.Name(), m.Name())):
            attr: cst.Attribute = original_node.func
            method: str = attr.attr.value

            if method == self.method_name:
                return self.replace_node


@dataclass
class SplitContext:
    expression_provider: cst.metadata.ExpressionContextProvider

    original_method_node: cst.FunctionDef
    original_method_desc: MethodDescriptor

    previous_block: Optional["StatementBlock"] = None
    next_block: Optional["StatementBlock"] = None

    def set_next_block(self, block: "StatementBlock"):
        self.next_block = block


class StatementBlock:
    def __init__(
        self,
        block_id: int,
        statements: List[cst.BaseStatement],
        split_context: SplitContext,
        class_invoked: Optional["ClassDescriptor"] = None,
        class_call_ref: Optional[str] = None,
        method_invoked: Optional[str] = None,
        call_args: Optional[List[cst.Arg]] = None,
        last_block: bool = False,
    ):
        self.block_id = block_id
        self.last_block = last_block
        self.returns = 0
        self.statements = statements
        self.split_context = split_context

        self.class_invoked = class_invoked
        self.method_invoked = method_invoked
        self.class_call_ref = class_call_ref
        self.call_args = call_args

        self.arguments_for_call = []

        # A list of Def/Use variables per statement line, in the order that they are declared/used.
        def_use: List[List[Union[Def, Use]]] = []

        # Remove whitespace if it's there.
        if m.matches(self.statements[0], m.TrailingWhitespace()):
            self.statements.pop(0)

        # If there is a previous block, to which this block is subsequent, we assume this is because of a method call.
        if self.split_context.previous_block:
            method_invoked = self.split_context.previous_block.method_invoked

        for statement in self.statements:
            stmt_analyzer = StatementAnalyzer(
                split_context.expression_provider, method_invoked
            )
            statement.visit(stmt_analyzer)

            def_use.append(stmt_analyzer.def_use)

            self.returns += stmt_analyzer.returns

        self.dependencies: List[str] = self._compute_dependencies(def_use)
        self.definitions: List[str] = self._compute_definitions(def_use)

        self.new_function: cst.FunctionDef = self.build()

    def _compute_definitions(
        self, def_use_list: List[List[Union[Def, Use]]]
    ) -> List[str]:
        """Computes the (unique) list of definitions in this block.
        This list is sorted in the order of declaration. In case, there are multiple

        :param def_use_list: the list of definitions/usages per statement in the block.
        :return:
        """
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

    def _get_invoked_method_descriptor(self) -> MethodDescriptor:
        return self.class_invoked.get_method_by_name(self.method_invoked)

    def fun_name(self) -> str:
        return f"{self.split_context.original_method_node.name.value}_{self.block_id}"

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
        # The definitions of this block, include the given parameters.
        self.definitions.extend(
            list(self.split_context.original_method_desc.input_desc.keys())
        )

        # We re-use part of the original function signature.
        fun_name: cst.Name = cst.Name(self.fun_name())
        params: cst.Parameters = self.split_context.original_method_node.params

        # Assignments for the call.
        argument_assignments = self._build_argument_assignments()

        self.arguments_for_call = [name for name, _ in argument_assignments]

        # Build the return statement.
        return_stmt: cst.Return = self._build_return(self.arguments_for_call)

        if m.matches(self.split_context.original_method_node.body, m.IndentedBlock()):
            final_body = (  # We build this first block as statements + assignments + return statement.
                self.statements
                + [assign for _, assign in argument_assignments]
                + [return_stmt]
            )

            function_body = self.split_context.original_method_node.body.with_changes(
                body=final_body
            )

        else:
            raise AttributeError(
                f"Expected the body of a function to be in an indented block, but got an {self.split_context.original_method_node.body}."
            )

        return self.split_context.original_method_node.with_changes(
            name=fun_name, params=params, body=function_body, returns=None
        )

    def _previous_call_result(self) -> cst.Name:
        return cst.Name(f"{self.split_context.previous_block.method_invoked}_return")

    def _build_intermediate_block(self) -> cst.FunctionDef:
        print(f"Building intermediate block {self.block_id}")
        # Function signature
        fun_name: cst.Name = cst.Name(self.fun_name())

        params: List[cst.Param] = [cst.Param(cst.Name(value="self"))]
        for usage in self.dependencies:
            params.append(cst.Param(cst.Name(value=usage)))

        # Get the result of the previous call as parameter of this block.
        previous_block_call: cst.Name = self._previous_call_result()
        params.append(cst.Param(previous_block_call))
        self.dependencies.append(self._previous_call_result().value)

        param_node: cst.Parameters() = cst.Parameters(tuple(params))

        # Assignments for the call.
        argument_assignments = self._build_argument_assignments()
        self.arguments_for_call = [name for name, _ in argument_assignments]

        # Build the return statement.
        return_stmt: cst.Return = self._build_return(self.arguments_for_call)

        self.statements[0] = self.statements[0].visit(
            ReplaceCall(
                self.split_context.previous_block.method_invoked,
                self._previous_call_result(),
            )
        )

        if m.matches(self.split_context.original_method_node.body, m.IndentedBlock()):
            final_body = (
                self.statements
                + [assign for _, assign in argument_assignments]
                + [return_stmt]
            )

            function_body = self.split_context.original_method_node.body.with_changes(
                body=final_body,
            )

        else:
            raise AttributeError(
                f"Expected the body of a function to be in an indented block, but got an {self.split_context.original_method_node.body}."
            )

        return self.split_context.original_method_node.with_changes(
            name=fun_name,
            params=param_node,
            body=function_body,
        )

    def _build_last_block(self) -> cst.FunctionDef:
        # Function signature
        fun_name: cst.Name = cst.Name(self.fun_name())

        params: List[cst.Param] = [cst.Param(cst.Name(value="self"))]
        for usage in self.dependencies:
            params.append(cst.Param(cst.Name(value=usage)))

        previous_block_call: cst.Name = self._previous_call_result()
        params.append(cst.Param(previous_block_call))

        # TODO Hacky, fix it.
        self.dependencies.append(self._previous_call_result().value)

        param_node: cst.Parameters() = cst.Parameters(tuple(params))
        returns_signature = self.split_context.original_method_node.returns

        self.statements[0] = self.statements[0].visit(
            ReplaceCall(
                self.split_context.previous_block.method_invoked,
                self._previous_call_result(),
            )
        )

        if m.matches(self.split_context.original_method_node.body, m.IndentedBlock()):
            final_body = self.statements

            function_body = self.split_context.original_method_node.body.with_changes(
                body=final_body,
            )

        else:
            raise AttributeError(
                f"Expected the body of a function to be in an indented block, but got an {self.split_context.original_method_node.body}."
            )

        return self.split_context.original_method_node.with_changes(
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
        else:
            return self._build_intermediate_block()
