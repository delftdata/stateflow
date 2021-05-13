import libcst as cst
from typing import List, Optional, Set, Tuple, Union, Dict
from src.descriptors.method_descriptor import MethodDescriptor
from src.descriptors.class_descriptor import ClassDescriptor
from src.dataflow.event_flow import (
    EventFlowNode,
    ReturnNode,
    RequestState,
    InvokeExternal,
    InvokeSplitFun,
    FunctionType,
)
import libcst.matchers as m
from dataclasses import dataclass, fields


@dataclass
class Def:
    """A wrapper for the 'definition' of a variable within a piece of code."""

    name: str


@dataclass
class Use:
    """A wrapper for the 'usage' of a variable within a piece of code."""

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
                and node.value != "print"
            ):
                self.def_use.append(Use(node.value))

    def visit_Return(self, node: cst.Return):
        """
        Keep track of all returns.
        """
        self.returns += 1


@dataclass
class SplitContext:
    """ We keep a SplitContext as context for parsing a set of statements into a StatementBlock."""

    # Mapping from class name to its descriptor, this is useful for some lookups.
    class_descriptors: Dict[str, ClassDescriptor]

    # This SplitContext has a top-level ExpressionContextProvider to identify LOAD and STORE Name nodes.
    expression_provider: cst.metadata.ExpressionContextProvider

    # Original method node and descriptor.
    original_method_node: cst.FunctionDef
    original_method_desc: MethodDescriptor

    # Class descriptor of the class this method split belongs to.
    class_desc: ClassDescriptor

    @classmethod
    def from_instance(cls, instance: "SplitContext", **kwargs):
        arguments = {}
        for field in fields(instance):
            arguments[field.name] = getattr(instance, field.name)

        arguments.update(kwargs)
        return cls(**arguments)


@dataclass
class InvocationContext:
    """Whenever a method is invoked, we keep track of its context so that StatementBlocks can be properly parsed.

    Attributes:
        :param class_desc: The ClassDescriptor of the (external) class of which a method is invoked.
        :param call_instance_var: The instance variable of the class of which a method is invoked.
        :param method_invoked: The name of the invoked method.
        :param method_desc: The descriptor of the invoked method.
        :param call_arguments: The actual parameters/arguments of this invocation.
    """

    class_desc: ClassDescriptor
    call_instance_var: str
    method_invoked: str
    method_desc: MethodDescriptor
    call_arguments: List[cst.Arg]


@dataclass
class FirstBlockContext(SplitContext):
    """This is the context for the first block.

    A first block only has a current invocation.
        I.e. it does not have to deal with the result of a 'previous'
        invocation.
    It might also be None, then we treat it as 'just' a block of computation which returns its definitions.
    """

    current_invocation: Optional[InvocationContext] = None


@dataclass
class IntermediateBlockContext(SplitContext):
    """This is the context for an intermediate block.

    An intermediate block has both a 'previous' and a 'current invocation'.
    1. For the previous invocation, it has to add the result as a parameter and replace the call with this result param.
    2. For the current invocation, it has to evaluate the arguments and return a MethodInvocationRequest.

    One or both might also be None, then we treat it as 'just' a block of computation which returns its definitions.
    """

    previous_invocation: Optional[InvocationContext] = None
    current_invocation: Optional[InvocationContext] = None


@dataclass
class LastBlockContext(SplitContext):
    """This is the context for the last block.

    A last block only has a previous invocation.
       I.e. it does not have to deal with the result of a 'current'
       invocation
    One or both might also be None, then we treat it as 'just' a block of computation.
    """

    previous_invocation: Optional[InvocationContext] = None


class Block:
    def __init__(
        self,
        block_id: int,
        split_context: SplitContext,
        previous_block: Optional["Block"] = None,
    ):
        self.block_id = block_id
        self.split_context = split_context

        # Keep track of the previous and next statement block.
        self.previous_block: Optional["Block"] = previous_block
        self.next_block: List["Block"] = []

        # Set the current block as next block for the previous one.
        if self.previous_block:
            self.previous_block.set_next_block(self)

        # Dependencies and definitions
        self.dependencies: List[str] = []
        self.definitions: List[str] = []

    def set_previous_block(self, block: "Block"):
        self.previous_block = block
        self.previous_block.set_next_block(self)

    def set_next_block(self, block: "Block"):
        """Sets the next Block.
        This needs to be set _after_ creating this SplitContext, since we don't know the next block until it is created.
        A block can have multiple next blocks, so they are stored in a list.

        :param block: the next statement block.
        """
        if block not in self.next_block:
            self.next_block.append(block)

    def _build_params(self) -> cst.Parameters:
        params: List[cst.Param] = [cst.Param(cst.Name(value="self"))]
        for usage in self.dependencies:
            params.append(cst.Param(cst.Name(value=usage)))

        # Get the result of the previous call as parameter of this block.
        if self.split_context.previous_invocation:  # only if this invocation exists.
            previous_block_call: cst.Name = self._previous_call_result()
            params.append(cst.Param(previous_block_call))
            self.dependencies.append(self._previous_call_result().value)

        param_node: cst.Parameters = cst.Parameters(tuple(params))

        return param_node

    def _previous_call_result(self) -> cst.Name:
        """Returns the Name node of the call result of the previously invoked function.
        It will be passed as a parameter for this block.
        """
        return cst.Name(
            f"{self.split_context.previous_invocation.method_invoked}_return"
        )


class StatementBlock(Block):
    def __init__(
        self,
        block_id: int,
        statements: List[cst.BaseStatement],
        split_context: Union[
            FirstBlockContext, IntermediateBlockContext, LastBlockContext
        ],
        previous_block: Optional["StatementBlock"] = None,
    ):
        super().__init__(block_id, split_context, previous_block)
        self.statements = statements
        self.split_context = split_context

        self.arguments_for_call = []
        self.returns = 0

        # A list of Def/Use variables per statement line, in the order that they are declared/used.
        self.def_use_list: List[List[Union[Def, Use]]] = []

        # Remove whitespace and analyze statements.
        self._remove_whitespace()
        self._analyze_statements()

        # Compute dependencies and definitions based on Def/Use list.
        self.dependencies: List[str] = self._compute_dependencies()
        self.definitions: List[str] = self._compute_definitions()

        # Build the _new_ FunctionDefinition.
        self.new_function: cst.FunctionDef = self.build_definition()

    def _analyze_statements(self):
        previous_invocation: Optional[InvocationContext] = (
            self.split_context.previous_invocation
            if not isinstance(self.split_context, FirstBlockContext)
            else None
        )

        for statement in self.statements:
            stmt_analyzer = StatementAnalyzer(
                self.split_context.expression_provider,
                self.split_context.previous_invocation.method_invoked
                if previous_invocation
                else None,
            )
            statement.visit(stmt_analyzer)

            self.def_use_list.append(stmt_analyzer.def_use)

            self.returns += stmt_analyzer.returns

    def _remove_whitespace(self):
        """ Removes whitespace from statements if it is there. """
        if len(self.statements) > 0 and m.matches(
            self.statements[0], m.TrailingWhitespace()
        ):
            self.statements.pop(0)

    def _compute_definitions(self) -> List[str]:
        """Computes the (unique) list of definitions in this block.
        This list is sorted in the order of declaration. In case, there are multiple

        :param def_use_list: the list of definitions/usages per statement in the block.
        :return:
        """
        definitions = []
        for def_use in self.def_use_list:
            for el in def_use:
                if isinstance(el, Def) and el.name not in definitions:
                    definitions.append(el.name)

        return definitions

    def _compute_dependencies(self) -> List[str]:
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
        for def_use in self.def_use_list:
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

    def fun_name(self) -> str:
        """Get the name of this function given the block id.
        :return: the (unique) name of this block.
        """
        return f"{self.split_context.original_method_node.name.value}_{self.block_id}"

    def _build_argument_assignments(
        self,
    ) -> List[Tuple[cst.Name, cst.SimpleStatementLine]]:
        assign_list: List[Tuple[cst.Name, cst.SimpleStatementLine]] = []
        for i, arg in enumerate(self.split_context.current_invocation.call_arguments):
            assign_value: cst.BaseExpression = arg.value

            # We name it based on the InputDescriptor of the invoked method.
            if m.matches(arg.keyword, m.Name()):
                assign_name: str = (
                    self.split_context.current_invocation.method_invoked
                    + "_"
                    + arg.keyword.value
                )
            else:
                assign_name: str = (
                    "invoke_"
                    + self.split_context.current_invocation.method_invoked
                    + "_arg_"
                    + self.split_context.current_invocation.method_desc.input_desc.keys()[
                        i
                    ]
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
                                        f"# Autogenerated assignments for the method call to: "
                                        f"{self.split_context.current_invocation.method_invoked}."
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
        for definition in self.definitions:
            return_names.append(cst.Name(value=definition))

        if self.split_context.current_invocation:
            call_arguments_names: str = ",".join([n.value for n in call_arguments])
            call_expression: cst.BaseExpression = cst.parse_expression(
                f"InvokeMethodRequest('{self.split_context.current_invocation.class_desc.class_name}', "
                f"{self.split_context.current_invocation.call_instance_var}, "
                f"'{self.split_context.current_invocation.method_invoked}', [{call_arguments_names}])"
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
        """Build the first block of this function.

        If we have a 'previous call':
            1. We copy the original function signature + parameters. This assumes that the code by the developer
                is 'correct'.
            2. We create a set of assignments for the arguments of the call
                (which is done after the execution of this first block).
            3. We return 'internal' definition and a InvokeMethodRequest wrapper.
        If no previous call:
            1. We copy the original function signature + parameters. This assumes that the code by the developer
                is 'correct'.
            2. We return 'internal' definition.

        :return: a new FunctionDefinition.
        """
        # The definitions of this block, include the given parameters.
        self.definitions.extend(
            list(self.split_context.original_method_desc.input_desc.keys())
        )

        # Step 1, copy original parameters.
        fun_name: cst.Name = cst.Name(self.fun_name())
        params: cst.Parameters = self.split_context.original_method_node.params

        # Step 2, assignments for the _next_ call.
        if self.split_context.current_invocation:
            argument_assignments = self._build_argument_assignments()
        else:
            argument_assignments = []
        self.arguments_for_call = [name for name, _ in argument_assignments]

        # Step 3, build the return statement.
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
                f"Expected the body of a function to be in an indented block, "
                f"but got an {self.split_context.original_method_node.body}."
            )

        return self.split_context.original_method_node.with_changes(
            name=fun_name, params=params, body=function_body, returns=None
        )

    def _build_intermediate_block(self) -> cst.FunctionDef:
        """Builds an intermediate block.

        If we have a 'previous call':
            1. We build a new parameter list for this block, this includes _all_ dependencies of this block
                + the return result of the call.
            2. We replace the Call node of the invocation which is executed _before_ this intermediate block, with an
                return variable from this call.
        If we don't have a previous call:
            1. We build a new parameter list for this block, this includes _all_ dependencies of this block.
        2/3. We create a set of assignments for the arguments of the next call
            (which is done after the execution of this intermediate block).
        3/4. We return the 'internal' definitions and a InvokeMethodRequest wrapper.

        :return: a new FunctionDefinition.
        """
        # If this block has an invocation to another class. We need to have that instance var as param.
        if self.split_context.current_invocation:
            self.dependencies.append(
                self.split_context.current_invocation.call_instance_var
            )

        # Function signature
        fun_name: cst.Name = cst.Name(self.fun_name())

        # Step 1, parameter node.
        param_node: cst.Parameters() = self._build_params()

        # Step 2, replace the _previous_ call.
        if self.split_context.previous_invocation:
            self.statements[0] = self.statements[0].visit(
                ReplaceCall(
                    self.split_context.previous_invocation.method_invoked,
                    self._previous_call_result(),
                )
            )

        # Step 2/3, assignments for the _next_ call.
        if self.split_context.current_invocation:
            argument_assignments = self._build_argument_assignments()
        else:
            argument_assignments = []
        self.arguments_for_call = [name for name, _ in argument_assignments]

        # Step 3/4, build the return statement.
        return_stmt: cst.Return = self._build_return(self.arguments_for_call)

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
        """Builds the last block.

        If we have a 'previous call':
            1. We build a new parameter list for this block, this includes _all_ dependencies of this block
                + the return result of the call.
            2. We replace the Call node of the invocation which is executed _before_ this last block, with an
                return variable from this call.
        If we don't have a previous call:
            1. We build a new parameter list for this block, this includes _all_ dependencies of this block.
        2/3. We keep the original return signature + return nodes.
        :return: a new FunctionDefinition.
        """

        fun_name: cst.Name = cst.Name(self.fun_name())

        # Step 1, parameter node.
        param_node: cst.Parameters() = self._build_params()

        # Step 2, replace the _previous_ call only if this previous call exists.
        if self.split_context.previous_invocation:
            self.statements[0] = self.statements[0].visit(
                ReplaceCall(
                    self.split_context.previous_invocation.method_invoked,
                    self._previous_call_result(),
                )
            )

        # Step 2/3, keep the original return signature.
        returns_signature = self.split_context.original_method_node.returns

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

    def build_event_flow_nodes(self, start_node: EventFlowNode) -> List[EventFlowNode]:
        # Initialize id and latest flow node.
        flow_node_id = start_node.id + 1  # Offset the id with start_node.
        latest_node: EventFlowNode = start_node

        # Initialize list of flow nodes for this StatementBlock.
        flow_nodes: List[EventFlowNode] = []

        # For re-use purposes, we define the FunctionType of the class this StatementBlock belongs to.
        class_type = self.split_context.class_desc.to_function_type()

        def update_flow_graph(new_node: EventFlowNode):
            nonlocal flow_nodes, latest_node, flow_node_id
            flow_nodes.append(new_node)

            # Set next and previous.
            latest_node.set_next(new_node.id)
            new_node.set_previous(latest_node.id)

            # Set latest.
            latest_node = new_node

            # Increment id.
            flow_node_id += 1

        # TODO, for the FirstBlock we now assume we always need to get state, we can omit this if we don't access state.
        if self.is_first():
            """For a first node, we assume the following scenario:
            1. We get the state of all stateful function parameters. (!!Improve this in an optimized version!!).
            2. We invoke the first part of the function (i.e. InvokeSplitFun node).
                2a. If this first part, has a return. We also add a return node.
            3. We invoke an external function (i.e. InvokeExternal node).
            """

            # Step 1, build the RequestState nodes; We match the input parameters to the correct.
            for (
                input_name,
                input_type,
            ) in self.split_context.original_method_desc.input_desc.get().items():
                matched_class = self.split_context.class_descriptors.get(input_type)

                if matched_class:
                    request_node = RequestState(
                        FunctionType.create(matched_class), flow_node_id, input_name
                    )

                    # Update the flow graph.
                    update_flow_graph(request_node)

            # Step 2, invoke the first part of the splitted function.
            split_node = InvokeSplitFun(
                class_type,
                flow_node_id,
                self.fun_name(),
                list(self.split_context.original_method_desc.input_desc.keys()),
                list(self.definitions),
                self.split_context.original_method_desc.get_typed_params(),
            )
            update_flow_graph(split_node)

            # Step 2a, we add an (extra) return node.
            if self.returns > 0:
                return_node = ReturnNode(flow_node_id)
                update_flow_graph(return_node)

                # Since the last node should be InvokeSplitFun (not ReturnNode), we update the latest node again.
                latest_node = split_node

            # Step 3, we add an InvokeExternal node.
            invoke_node = InvokeExternal(
                FunctionType.create(
                    self.split_context.class_descriptors[
                        self.split_context.current_invocation.class_desc.class_name
                    ]
                ),
                flow_node_id,
                self.split_context.current_invocation.call_instance_var,
                self.split_context.current_invocation.method_invoked,
                list(
                    self.split_context.current_invocation.method_desc.input_desc.keys()
                ),
            )

            update_flow_graph(invoke_node)
        elif self.is_last():
            """For a last node, we assume the following scenario:
            1. We invoke the last part of the function (i.e. InvokeSplitFun).
            2. We add a ReturnNode.
            """

            # Step 1, build the last part of the splitted function.
            split_node = InvokeSplitFun(
                class_type,
                flow_node_id,
                self.fun_name(),
                self.dependencies,
                [],  # We don't care about the definitions for the last block!
                self.split_context.original_method_desc.get_typed_params(),  # TODO Is this possible?
            )

            update_flow_graph(split_node)

            # Step 2, build the return node.
            return_node = ReturnNode(flow_node_id)
            update_flow_graph(return_node)
        else:
            """For an intermediate node, we assume the following scenario:
            1. We invoke an intermediate part of the function (i.e. InvokeSplitFun).
                1a. If this first part, has a return. We also add a return node.
            2. We invoke an external function (i.e. InvokeExternal node).
            """
            # Step 1, invoke the first part of the splitted function.
            split_node = InvokeSplitFun(
                class_type,
                flow_node_id,
                self.fun_name(),
                self.dependencies,
                list(self.definitions),
                self.split_context.original_method_desc.get_typed_params(),
            )
            update_flow_graph(split_node)

            # Step 2a, we add an (extra) return node.
            if self.returns > 0:
                return_node = ReturnNode(flow_node_id)
                update_flow_graph(return_node)

                # Since the last node should be InvokeSplitFun (not ReturnNode), we update the latest node again.
                latest_node = split_node

            # Step 3, we add an InvokeExternal node.
            invoke_node = InvokeExternal(
                FunctionType.create(
                    self.split_context.class_descriptors[
                        self.split_context.current_invocation.class_desc.class_name
                    ]
                ),
                flow_node_id,
                self.split_context.current_invocation.call_instance_var,
                self.split_context.current_invocation.method_invoked,
                list(
                    self.split_context.current_invocation.method_desc.input_desc.keys()
                ),
            )

            update_flow_graph(invoke_node)

        return flow_nodes

    def is_first(self) -> bool:
        """Returns if this StatementBlock is the first block.
        :return: True or False.
        """
        return isinstance(self.split_context, FirstBlockContext)

    def is_last(self) -> bool:
        """Returns if this StatementBlock is the last block.
        :return: True or False.
        """
        return isinstance(self.split_context, LastBlockContext)

    def build_definition(self) -> cst.FunctionDef:
        """Builds a new FunctionDefinition based on this StatementBlock.

        Has a different treatment for either First, Last or Intermediate Blocks.
        :return: a FunctionDefinition.
        """
        if self.is_first():
            return self._build_first_block()
        elif self.is_last():
            return self._build_last_block()
        else:
            return self._build_intermediate_block()


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
