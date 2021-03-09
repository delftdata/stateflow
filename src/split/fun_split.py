import operator

import math
import inspect
from typing import List, Tuple
import textwrap
import astpretty
import astor
from functools import reduce
import gast as ast
from example import *
import beniget
from capture_statement import CaptureStatement


def flatten(input):
    return [item for sublist in input for item in sublist]


class Call:
    def __init__(
        self,
        identifier: str,
        call_args: List[ast.expr],
        call_args_kw: List[ast.keyword],
        has_return: bool,
    ):
        self.identifier = identifier
        self.call_args = call_args
        self.call_args_kw = call_args_kw
        self.has_return = has_return

    def build_assignments(self) -> List[Tuple[str, ast.Assign]]:
        positional_args = [
            self.construct_assignment(f"{self.identifier}_arg_{i}", arg_expr)
            for i, arg_expr in enumerate(self.call_args)
        ]

        keyword_args = [
            self.construct_assignment(f"{self.identifier}_arg_{arg.arg}", arg.value)
            for arg in self.call_args_kw
        ]

        return positional_args + keyword_args

    @staticmethod
    def construct_assignment(
        identifier: str, expression: ast.expr
    ) -> Tuple[str, ast.Assign]:
        assign_name = ast.Name(identifier, ast.Store(), None, None)
        return identifier, ast.Assign([assign_name], expression)


class Statement:
    def __init__(
        self,
        contains_call: bool,
        definitions: List[str],
        usages: List[str],
        node,
        call: Call,
        empty: bool,
    ):
        self.contains_call = contains_call
        self.node = node
        self.definitions = definitions
        self.usages = usages
        self.call = call
        self.empty = empty

    def is_assign(self):
        return len(self.definitions)

    @staticmethod
    def unpack_tuple(node: ast.Tuple) -> List[str]:
        return list([n.id for n in node.elts if isinstance(n, ast.Name)])

    @staticmethod
    def parse_assign_target(target) -> List[str]:
        if isinstance(target, list):
            return [Statement.parse_assign_target(t) for t in target]
        if isinstance(target, ast.Tuple):
            return Statement.unpack_tuple(target)
        elif isinstance(target, ast.Name):
            return [target.id]
        else:
            raise ValueError(f"Expected an ast.Name or ast.Tuple but got {target}.")

    @staticmethod
    def parse_statement(ast_node) -> "Statement":

        capture_statement = CaptureStatement(ast_node)
        capture_statement.visit(ast_node)

        if capture_statement.has_call:
            call = Call(
                capture_statement.call_identifier,
                capture_statement.call_args,
                capture_statement.call_args_kw,
                True,
            )
        else:
            call = None
        return Statement(
            capture_statement.has_call,
            capture_statement.definitions,
            capture_statement.usages,
            ast_node,
            call,
            capture_statement.empty_statement,
        )


class StatementBlock:
    def __init__(self, stmts: List[Statement]):
        self.stmts: List[Statement] = stmts
        self.extra_nodes: List = []
        self.last_block: bool = False
        self.extra_definitions: List[str] = []

    def get_definitions(self) -> List[str]:
        assign_list = list(
            set([item for stmt in self.stmts for item in stmt.definitions])
        )
        return assign_list + self.extra_definitions

    def get_arguments(self) -> ast.arguments:
        args = []
        self_arg = ast.Name("self", ast.Param(), None, None)

        args.append(self_arg)

        for arg in self.get_usages():
            args.append(ast.Name(arg, ast.Param(), None, None))

        arguments = ast.arguments(args, [], None, [], [], None, [])

        return arguments

    def get_return_statement(self) -> ast.Return:
        assign_list = self.get_definitions()

        if len(assign_list) == 0:
            return ast.Return(None)

        assigns = [ast.Name(name, ast.Load(), None, None) for name in assign_list]

        if len(assigns) == 1:
            return_body = assigns[0]
        else:
            return_body = ast.Tuple(assigns, ast.Load())

        return ast.Return(return_body)

    def get_calls(self):
        return [
            stmt.call for stmt in self.stmts if stmt.contains_call and not stmt.empty
        ]

    def get_usages(self):
        usages = list(set([item for stmt in self.stmts for item in stmt.usages]))
        calls = self.get_calls()

        if len(calls) > 1:
            raise AttributeError(
                f"We can only have 1 call in a statement block. We got {len(calls)}."
            )

        call_results = []
        if len(calls) == 1 and calls[0].has_return:
            call_results.append(f"{calls[0].identifier}_result")

        return usages + call_results

    def clear_usages(self):
        for i, stmt in enumerate(self.stmts):
            if i == 0:
                continue

            previous_definitions = flatten([stm.definitions for stm in self.stmts[:i]])
            for usage in stmt.usages:
                if usage in previous_definitions:
                    stmt.usages.remove(usage)

    def add_extra_nodes(self, more_nodes):
        self.extra_nodes = self.extra_nodes + more_nodes

    def nodes(self):
        if self.last_block:
            return list([s.node for s in self.stmts if not s.empty]) + self.extra_nodes
        else:
            return list(
                [s.node for s in self.stmts if not s.empty]
                + self.extra_nodes
                + [self.get_return_statement()]
            )


def is_call(ast_node):
    if isinstance(ast_node, ast.Assign):
        expr_value = ast_node.value
        for sub_node in ast.walk(expr_value):
            if isinstance(sub_node, ast.Call):
                return True
    return False


def compute_break_points(body) -> List[StatementBlock]:
    parsed_stmts = [Statement.parse_statement(stmt) for stmt in body]
    all_blocks = []
    current_stmt_list = []
    for i, stmt in enumerate(parsed_stmts):
        if stmt.contains_call:
            statement_block = StatementBlock(current_stmt_list)
            all_blocks.append(statement_block)
            current_stmt_list = []

            # Now also ensure that the arguments of the call are evaluated
            call_arguments = stmt.call.build_assignments()
            statement_block.add_extra_nodes([arg for arg_id, arg in call_arguments])
            statement_block.extra_definitions = [
                arg_id for arg_id, arg in call_arguments
            ] + statement_block.extra_definitions

        current_stmt_list.append(stmt)

    all_blocks.append(StatementBlock(current_stmt_list))
    return all_blocks


def split_functions(fun: ast.FunctionDef) -> List[ast.FunctionDef]:
    stmts = compute_break_points(fun.body)

    # Set last statement
    stmts[-1].last_block = True

    fun_name = fun.name

    # Handle the first set of statements
    fun_1 = stmts[0]
    fun_1.clear_usages()
    fun.name = fun_name + "_0"

    fun.body = fun_1.nodes()
    final_funs = [fun]

    for i, stmt in enumerate(stmts[1:]):
        stmt.clear_usages()

        # Input
        arguments = stmt.get_arguments()

        # Output
        body = stmt.nodes()

        fun_def = ast.FunctionDef(
            f"{fun_name}_{i + 1}", arguments, body, [], None, None
        )
        final_funs.append(fun_def)

    return final_funs


calculator = Calculator(1)
code = """
def computation(self, y: int):
    a = d = self.x + y
    q = y
    c = 3
    if sqrt(c) == 1:
        c = sqrt(d)
    return c
"""
fun_def = ast.parse(textwrap.dedent(inspect.getsource(calculator.computation.__code__)))

statements = split_functions(fun_def.body[0])


# compile(statements[0], __file__, mode="exec")
# print(astor.dump_tree(statements[0]))
print(
    f"ORIGINAL: \n {textwrap.dedent(inspect.getsource(calculator.computation.__code__))}"
)
print("NEW:")
for stmt in statements:
    print(astor.code_gen.to_source(ast.gast_to_ast(stmt)))

# TODO
# Fix actual assignments for a function call
# Erase actual method call and add return result (as parameter) and override calls with Name()
