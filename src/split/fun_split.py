import operator

import math
import inspect
from typing import List
import textwrap
import astpretty
import astor
from functools import reduce
import gast as ast
from example import *
import beniget


class Statement:
    def __init__(self, contains_call: bool, node):
        self.contains_call = contains_call
        self.node = node
        self.definitions = []
        self.usages = []

        for sub_node in ast.walk(node):
            if isinstance(sub_node, ast.Name):
                if isinstance(sub_node.ctx, ast.Store):
                    self.definitions.append(sub_node.id)
                elif isinstance(sub_node.ctx, ast.Load):
                    self.usages.append(sub_node.id)

        print(f"definitions: {self.definitions}")
        print(f"usages: {self.usages}")
        print("")

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
        contains_call = False

        if (
            isinstance(ast_node, ast.Assign)
            or isinstance(ast_node, ast.AugAssign)
            or isinstance(ast_node, ast.AnnAssign)
        ):

            if ast_node.value:
                for val_child in ast.walk(ast_node.value):
                    if isinstance(val_child, ast.Call):
                        contains_call = True

        return Statement(contains_call, ast_node)


class StatementBlock:
    def __init__(self, stmts: List[Statement]):
        self.stmts = stmts

    def get_assignments(self) -> List[str]:
        assign_list = list(
            set([item for stmt in self.stmts for item in stmt.definitions])
        )
        return assign_list

    def get_arguments(self) -> ast.arguments:
        args = []
        self_arg = ast.Name("self", ast.Param(), None, None)

        args.append(self_arg)

        for arg in self.get_usages():
            args.append(ast.Name(arg, ast.Param(), None, None))

        arguments = ast.arguments(
            args,
        )

        pass

    def get_return_statement(self) -> ast.Return:
        assign_list = self.get_assignments()

        if len(assign_list) == 0:
            return ast.Return(None)

        assigns = [ast.Name(name, ast.Load(), None, None) for name in assign_list]

        if len(assigns) == 1:
            return_body = assigns[0]
        else:
            return_body = ast.Tuple(assigns, ast.Load())

        return ast.Return(return_body)

    def get_usages(self):
        return list(set([item for stmt in self.stmts for item in stmt.usages]))

    def nodes(self):
        return list([s.node for s in self.stmts] + [self.get_return_statement()])


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

    # astpretty.pprint(
    print(fun.args.args[0].ctx)

    fun.body = fun_1.nodes()
    final_funs = [fun]

    for stmt in stmts[1:]:
        # Usages
        stmt.get_usages()

        # Definitions
        return_node = stmt.get_return_statement()
        print(return_node.value)

    return final_funs


calculator = Calculator(1)
code = """
def computation(self, y: int):
    a = d = self.x + y
    q = y
    c = 3
    b = sqrt(a)
    c = a + b + d
    return c
"""
fun_def = ast.parse(code)

print(ast.parse("return").body[0].value)
ast.Return(ast.Name("a", ast.Load(), None, None))

statements = split_functions(fun_def.body[0])


# compile(statements[0], __file__, mode="exec")
print(statements[0])
# print(astor.dump_tree(statements[0]))
print(astor.code_gen.to_source(ast.gast_to_ast(statements[0])))

# TODO
# 1. Identify block of statements
# 2. Get input and output of statement blocks
# 3. Identify which functions need to be called.
# 4.
