import ast

from src.descriptors import ClassDescriptor, MethodDescriptor
from typing import List, Optional, Any, Set, Tuple
import libcst as cst
import libcst.matchers as m


class SplitTransformer(cst.CSTTransformer):
    def __init__(self):
        pass

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.CSTNode:
        print("HERE")


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
    def __init__(self, expression_provider):
        self.expression_provider = expression_provider

        self.definitions: List[str] = []
        self.usages: List[str] = []

        self.returns = 0

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
                and node.value != ("True" and "False")
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


class InvokeMethodRequest:
    def __init__(self, class_name: str, method_to_invoke: str, args: List[Any]):
        self.class_name = class_name
        self.method_to_invoke = method_to_invoke
        self.args = args


class StatementBlock:
    def __init__(
        self,
        block_id: int,
        expression_provider,
        statements: List[cst.BaseStatement],
        original_method: cst.FunctionDef,
        method_desc: MethodDescriptor,
        class_invoked: Optional[ClassDescriptor] = None,
        method_invoked: Optional[str] = None,
        call_args: Optional[List[cst.Arg]] = None,
        last_block: Optional["StatementBlock"] = False,
    ):
        self.block_id = block_id
        self.last_block: bool = last_block
        self.returns = 0
        self.original_method = original_method
        self.method_desc = method_desc

        self.statements = statements

        self.class_invoked = class_invoked
        self.method_invoked = method_invoked
        self.call_args = call_args

        definitions: List[str] = []
        usages: List[str] = []

        for statement in self.statements:
            stmt_analyzer = StatementBlockAnalyzer(expression_provider)
            statement.visit(stmt_analyzer)

            # Merge usages and definitions
            definitions.extend(stmt_analyzer.definitions)
            usages.extend(stmt_analyzer.usages)

            self.returns += stmt_analyzer.returns

        self.definitions: Set[str] = set(definitions)
        self.usages: Set[str] = set(usages)

        self.new_function: cst.FunctionDef = self.build()

    def _get_invoked_method_descriptor(self) -> MethodDescriptor:
        return self.class_invoked.get_method_by_name(self.method_invoked)

    def _build_argument_assignments(self) -> List[Tuple[cst.Name, cst.Assign]]:
        assign_list: List[Tuple[cst.Name, cst.Assign]] = []
        for i, arg in enumerate(self.call_args):
            assign_value: cst.BaseExpression = arg.value

            # We name it based on the InputDescriptor of the invoked method.
            if m.matches(arg.keyword, m.Name()):
                assign_name: str = self.method_invoked + "_" + arg.keyword.value
            else:
                assign_name: str = (
                    self.method_invoked
                    + "_"
                    + self._get_invoked_method_descriptor().input_desc.keys()[i]
                )

            target_name: cst.Name = cst.Name(value=assign_name)
            target: cst.AssignTarget = cst.AssignTarget(target_name)

            assign_list.append((target_name, cst.Assign([target], value=assign_value)))
        return assign_list

    def _build_return(self, call_arguments: List[cst.Name]) -> cst.Return:
        return_names: List[cst.BaseExpression] = []
        for definition in self.definitions:
            return_names.append(cst.Name(value=definition))

        call_arguments_names: List[str] = [n.value for n in call_arguments]
        call_expression: cst.BaseExpression = cst.parse_expression(
            f"InvokeMethodRequest({self.class_invoked.class_name}, {self.method_invoked}, {call_arguments_names})"
        )

        return_names.append(call_expression)

        if len(return_names) == 1:
            return cst.Return(return_names[0])
        else:
            return cst.Return(cst.Tuple([cst.Element(name) for name in return_names]))

    def _build_first_block(self) -> cst.FunctionDef:
        self.definitions = self.definitions.union(self.method_desc.input_desc.keys())

        diff_usages_def = self.usages.difference(self.definitions)
        if len(
            diff_usages_def
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

            function_body = cst.IndentedBlock(
                body=final_body,
                header=self.original_method.body.header,
                indent=self.original_method.body.indent,
                footer=self.original_method.body.footer,
            )

        else:
            raise AttributeError(
                f"Expected the body of a function to be in an indented block, but got an {self.original_method.body}."
            )

        return cst.FunctionDef(fun_name, params, function_body)

    def _previous_call_result(self) -> cst.Name:
        return cst.Name(f"{self.last_block.method_invoked}_return")

    def _build_last_block(self) -> cst.FunctionDef:
        # Function signature
        fun_name: cst.Name = cst.Name(
            f"{self.original_method.name.value}_{self.block_id}"
        )

        params: List[cst.Param] = []
        for usage in self.usages:
            params.append(cst.Param(cst.Name(value=usage)))

        previous_block_call: cst.Name = self._previous_call_result()
        params.append(cst.Param(previous_block_call))

        param_node: cst.Parameters() = cst.Parameters(params)
        returns_signature = self.original_method.returns

        self.statements[0] = self.statements[0].visit(
            RemoveCall(self.last_block.method_invoked, self._previous_call_result())
        )

        if m.matches(self.original_method.body, m.IndentedBlock()):
            final_body = self.statements

            function_body = cst.IndentedBlock(
                body=final_body,
                header=self.original_method.body.header,
                indent=self.original_method.body.indent,
                footer=self.original_method.body.footer,
            )

        else:
            raise AttributeError(
                f"Expected the body of a function to be in an indented block, but got an {self.original_method.body}."
            )

        return cst.FunctionDef(fun_name, params, function_body, returns_signature)

    def build(self) -> cst.FunctionDef:
        # We know this is the 'first' block in the flow.
        # We can simple use the same signature as the original function.
        if self.block_id == 0 and not self.last_block:
            return self._build_first_block()
        elif self.last_block:
            return self._build_last_block()


class Split:
    def __init__(self, descriptors: List[ClassDescriptor]):
        self.descriptors = descriptors

    def find_descriptor_by_name(self, class_name: str):
        return [desc for desc in self.descriptors if desc.class_name == class_name][0]

    def split_methods(self):
        for desc in self.descriptors:
            for method in desc.methods_dec:
                if method.has_links():
                    print(
                        f"{method.method_name} has links to other classes/functions. Now analyzing:"
                    )

                    SplitAnalyzer(
                        self,
                        desc.class_node,
                        method.method_node,
                        method,
                        desc.expression_provider,
                    )
