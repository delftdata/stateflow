import ast
import astor
import inspect


def sqrt(a: int) -> int:
    return a ** 2


class Fun:
    def __init__(self, id: int):
        self.id = id

    def compute(self, a: int) -> int:
        c = a * self.id

        def x():
            return 3

        d = sqrt(c)
        e = d + self.id
        return e


def identify_calls(fun_def: ast.FunctionDef):
    for n in fun_def.body:
        visit_stmt(n)


def visit_expr(expr):
    print(expr)


# Following AST declaration here: https://docs.python.org/3/library/ast.html
def visit_stmt(stmt):

    if isinstance(stmt, ast.Return):
        if stmt.value:
            visit_expr(stmt.value)
        pass
    elif isinstance(stmt, ast.Delete):
        pass
    else:
        # We don't consider:
        # FunctionDef, AsyncFunctionDef, ClassDef,
        #
        pass


class FindCalls(astor.tree_walk.TreeWalk):
    def __init__(self, node):
        super().__init__(node=node)


# Get the compute function definition.
class_def = ast.parse(inspect.getsource(Fun))
fun_defs = list([x for x in ast.walk(class_def) if isinstance(x, ast.FunctionDef)])
compute_fun_def = list([x for x in fun_defs if x.name == "compute"])

find_calls = FindCalls(class_def)
find_calls.visit()

identify_calls(compute_fun_def[0])
