import math
import ast
import inspect
from typing import List
import textwrap
import astpretty
import astor


def sqrt(x: int) -> int:
    return math.sqrt(x)


class Calculator:
    def __init__(self, x: int):
        self.x = x

    def computation(self, y: int):
        a = self.x + y
        b = sqrt(a)
        c = a + b
        return c

    def computation_1(self, y):
        a = self.x + y
        return a

    def computation_2(self, a, sqrt_result):
        b = sqrt_result
        c = a + b
        return c


def is_call(ast_node):
    if isinstance(ast_node, ast.Assign):
        expr_value = ast_node.value
        if isinstance(expr_value, ast.Call):
            return True
    return False


def split_functions(fun: ast.FunctionDef) -> List[ast.FunctionDef]:
    all_funs = []

    current_stmts = []
    for statement in fun.body:
        if is_call(statement):
            all_funs.append(list(current_stmts))
            current_stmts = []
        current_stmts.append(statement)
    all_funs.append(list(current_stmts))

    # Handle the first set of statements
    fun_1 = all_funs[0]
    assigns = []
    for statement in fun_1:
        if isinstance(statement, ast.Assign) and isinstance(
            statement.targets[0], ast.Name
        ):
            assigns.append(statement.targets[0].id)

    assigns = [ast.Name(name, ast.Load()) for name in assigns]
    fun.name = fun.name + "_1"
    if len(assigns) == 1:
        fun_1.append(ast.Return(assigns[0]))
    else:
        fun_1.append(ast.Return(ast.Tuple(assigns, ast.Load())))

    fun.body = fun_1
    final_funs = [fun]

    return final_funs


calculator = Calculator(1)
fun_def = ast.parse(textwrap.dedent(inspect.getsource(calculator.computation.__code__)))

print(ast.parse("return a, b, c").body[0].value.ctx)
ast.Return(ast.Name("a", ast.Load()))
statements = split_functions(fun_def.body[0])

# compile(statements[0], __file__, mode="exec")
print(statements[0])
# print(astor.dump_tree(statements[0]))
print(astor.code_gen.to_source(statements[0]))
