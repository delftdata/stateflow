import operator

import math
import ast
import inspect
from typing import List
import textwrap
import astpretty
import astor
from functools import reduce


def sqrt(x: int) -> int:
    return math.sqrt(x)


class Calculator:
    def __init__(self, x: int):
        self.x = x

    def computation(self, y: int):
        a = d = self.x + y
        q = y
        c = 3
        b = sqrt(a)
        c = a + b + d
        return c

    def computation_1(self, y):
        a = self.x + y
        return a

    def computation_2(self, a, sqrt_result):
        b = sqrt_result
        c = a + b
        return c


class Statement:
    def __init__(
        self, contains_call: bool, is_assign: bool, assign_list: List[str], node
    ):
        self.contains_call = contains_call
        self.is_assign = is_assign
        self.assign_list = reduce(list.__add__, assign_list, [])
        self.node = node

        print(self.assign_list)

    # if len(assign_list)

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
        contains_call = False
        is_assign = False
        assign_list = []

        if (
            isinstance(ast_node, ast.Assign)
            or isinstance(ast_node, ast.AugAssign)
            or isinstance(ast_node, ast.AnnAssign)
        ):
            is_assign = True
            target = (
                ast_node.targets
                if isinstance(ast_node, ast.Assign)
                else ast_node.target
            )

            assign_list = Statement.parse_assign_target(target)

            if ast_node.value:
                for val_child in ast.walk(ast_node.value):
                    if isinstance(val_child, ast.Call):
                        contains_call = True

        return Statement(contains_call, is_assign, assign_list, ast_node)


class StatementBlock:
    def __init__(self, stmts: List[Statement]):
        self.stmts = stmts

    def set_return_statement(self):
        assign_list = list(
            set([item for stmt in self.stmts for item in stmt.assign_list])
        )

        if len(assign_list) == 0:
            return ast.Return(None)

        assigns = [ast.Name(name, ast.Load()) for name in assign_list]

        if len(assigns) == 1:
            return_body = assigns[0]
        else:
            return_body = ast.Tuple(assigns, ast.Load())

        return ast.Return(return_body)

    def nodes(self):
        return list([s.node for s in self.stmts] + [self.set_return_statement()])


def is_call(ast_node):
    if isinstance(ast_node, ast.Assign):
        expr_value = ast_node.value
        if isinstance(expr_value, ast.Call):
            return True
    return False


def compute_break_points(body) -> List[StatementBlock]:
    parsed_stmts = [Statement.parse_statement(stmt) for stmt in body]
    all_blocks = []
    current_stmt_list = []
    for stmt in parsed_stmts:
        if stmt.contains_call:
            all_blocks.append(StatementBlock(current_stmt_list))
            current_stmt_list = []

        current_stmt_list.append(stmt)

    all_blocks.append(StatementBlock(current_stmt_list))
    return all_blocks


def split_functions(fun: ast.FunctionDef) -> List[ast.FunctionDef]:
    stmts = compute_break_points(fun.body)

    # Handle the first set of statements
    fun_1 = stmts[0]
    fun.name = fun.name + "_1"

    fun.body = fun_1.nodes()
    final_funs = [fun]

    return final_funs


calculator = Calculator(1)
fun_def = ast.parse(textwrap.dedent(inspect.getsource(calculator.computation.__code__)))

print(ast.parse("return").body[0].value)
ast.Return(ast.Name("a", ast.Load()))
statements = split_functions(fun_def.body[0])

# compile(statements[0], __file__, mode="exec")
print(statements[0])
# print(astor.dump_tree(statements[0]))
print(astor.code_gen.to_source(statements[0]))


# TODO
# 1. Identify block of statements
# 2. Get input and output of statement blocks
# 3. Identify which functions need to be called.
# 4.
