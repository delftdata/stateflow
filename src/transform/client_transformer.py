import libcst as cst
import libcst.matchers as m
from libcst.helpers import parse_template_expression
from typing import Optional, Union


class ClientMeta(type):
    def __new__(cls, *args, **kwargs):
        pass


class ClientTransformer(cst.CSTTransformer):
    def __init__(self, module_node: cst.CSTNode):
        self.module_node = module_node

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> Union[cst.BaseStatement, cst.RemovalSentinel]:
        import_future = "from concurrent.futures import Future"
        import_node = cst.parse_statement(import_future)

        body_node = updated_node.body.with_changes(body=[import_node])

        # return updated_node.with_changes(body=body_node)
        return updated_node.with_changes(body=body_node)

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> Union[cst.BaseStatement, cst.RemovalSentinel]:

        if m.matches(original_node.returns, m.Annotation()):
            updated_annotation = self._wrap_future_return_node(original_node.returns)
        else:
            updated_annotation = None

        # Pass all function defs.
        pass_node = cst.SimpleStatementLine(body=[cst.Pass()])
        body_node = updated_node.body.with_changes(body=[pass_node])

        return updated_node.with_changes(returns=updated_annotation, body=body_node)

    def _wrap_future_return_node(self, returns: cst.Annotation) -> cst.Annotation:
        """Wraps the return annotation in a Future.

        :param returns:
        :return:
        """

        # And wrap it in a future. This is quite a hacky way, maybe come up with something better here.
        future_node = parse_template_expression(
            "Future[{base_expr}]", base_expr=returns.annotation
        )
        return returns.with_changes(annotation=future_node)


from example.shop import User
import inspect


class Hoi:
    from concurrent.futures import Future

    def __init__(self):
        pass


module = cst.parse_module(inspect.getsource(User))
print(module)
transformer = ClientTransformer(module)

modified = module.visit(transformer)
print(modified.code)
