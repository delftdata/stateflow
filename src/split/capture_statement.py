import gast as ast
import beniget
from split_data import Call
from typing import List


class CaptureStatement(ast.NodeTransformer):
    def __init__(self, stmt_node):
        self.node = stmt_node

        self.ancestors = beniget.Ancestors()
        self.ancestors.visit(stmt_node)

        # Call related data.
        self.calls = []

        self.has_call = False
        self.empty_statement = False

        self.definitions = []
        self.usages = []

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.definitions.append(node.id)
        elif isinstance(node.ctx, ast.Load):
            self.usages.append(node.id)

        return node

    def visit_Call(self, node):
        if self.has_call:
            raise AttributeError("Multiple calls in one statement. Aborting.")

        # Get call parameter expressions
        self.has_call = True

        # Get function identifier.
        # We assume it to be:
        # 1. call_fun(arg_1, arg_2) etc.
        # 2. item.call_fun(arg_1, arg_2)
        # Stuff like Item().call_fun() is not yet supported.
        if isinstance(node.func, ast.Name):
            call_identifier = node.func.id
        elif isinstance(node.func, ast.Attribute) and isinstance(
            node.func.value, ast.Name
        ):
            call_identifier = node.func.attr
        else:
            raise AttributeError(
                f"Expected the call function to be an Attribute or Name, but got {node.func}"
            )

        self.calls.append(Call(call_identifier, node.args, node.keywords, True))

        if isinstance(self.ancestors.parent(node), ast.Expr):
            print(f"I'm here for the call {call_identifier}")
            print(self.ancestors.parent(node))
            self.empty_statement = True
            return node

        # If it HAS a return
        if True:
            name_node = ast.Name(call_identifier + "_result", ast.Load(), None, None)
            return name_node

        return


def get_usages(value: ast.Expr) -> List[str]:
    usages: List[str] = []
    for node in ast.walk(value):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            usages.append(node.id)
    return usages
