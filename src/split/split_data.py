from typing import List, Tuple
import gast as ast


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
