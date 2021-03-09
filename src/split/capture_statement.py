import gast as ast
import beniget


class CaptureStatement(ast.NodeVisitor):
    def __init__(self, stmt_node):
        self.node = stmt_node

        self.ancestors = beniget.Ancestors()
        self.ancestors.visit(stmt_node)

        # Call related data.
        self.has_call = False
        self.call_identifier = ""
        self.call_args = []
        self.call_args_kw = []

        self.definitions = []
        self.usages = []

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.definitions.append(node.id)
        elif isinstance(node.ctx, ast.Load):
            self.usages.append(node.id)

    def visit_Call(self, node):
        if self.has_call:
            raise AttributeError("Multiple calls in one statement. Aborting.")

        # Get call parameter expressions
        self.has_call = True
        self.call_args = node.args
        self.call_args_kw = node.keywords

        # Get function identifier.
        # We assume it to be:
        # 1. call_fun(arg_1, arg_2) etc.
        # 2. item.call_fun(arg_1, arg_2)
        # Stuff like Item().call_fun() is not yet supported.
        if isinstance(node.func, ast.Name):
            self.call_identifier = node.func.id
        elif isinstance(node.func, ast.Attribute) and isinstance(
            node.func.value, ast.Name
        ):
            self.call_identifier = node.func.attr
        else:
            raise AttributeError(
                f"Expected the call function to be an Attribute or Name, but got {node.func}"
            )

        print(f"Direct parent: {self.ancestors.parent(node)}")

        # If it HAS a return
        if True:
            name_node = ast.Name(
                self.call_identifier + "_result", ast.Load(), None, None
            )
            return name_node

        return
