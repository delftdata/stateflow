import ast


def var_contains_assign(var: str, node) -> bool:
    """Verifies if an AS(sub-)Tree contains assignment to the variable 'var'.
    This could be used to verify if a function, updates it's internal state (or is read-only).

    If assigned to an Attribute, we also evaluate the id of the Name identifier (if it's there).
    For example, for the piece of code `self.x = 3` you can check assignment for `self.x` OR `x`.
    However, `(expression).x` can only be recognized by `x`.

    :param var: the var to check for assignment.
    :param node: the AST.
    :return: True if it contains an assignment to var, otherwise False.
    """
    for child_node in ast.walk(node):
        if (
            isinstance(child_node, ast.Assign)
            or isinstance(child_node, ast.AnnAssign)
            or isinstance(child_node, ast.AugAssign)
        ):
            target = (
                child_node.targets[0]
                if isinstance(child_node, ast.Assign)
                else child_node.target
            )
            if isinstance(target, ast.Name) and target.id == var:
                return True
            elif isinstance(target, ast.Tuple) and len(
                [x.id for x in target.elts if isinstance(x, ast.Name) and x.id == var]
            ):
                return True
            elif isinstance(target, ast.Attribute):
                if (
                    isinstance(target.value, ast.Name)
                    and target.value.id + "." + target.attr == var
                ):
                    return True
                elif target.attr == var:
                    return True

    return False
