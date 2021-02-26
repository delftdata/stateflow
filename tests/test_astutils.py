import src.utils.astutils
import ast
import pytest

simple_assign = "x = 3"
simple_aug_assign = "x, y = 3"
simple_ann_assign = "x: int = 3"


def test_var_contains_assign_positive():
    assert src.utils.astutils.var_contains_assign("x", ast.parse(simple_assign))
    assert src.utils.astutils.var_contains_assign("x", ast.parse(simple_aug_assign))
    assert src.utils.astutils.var_contains_assign("y", ast.parse(simple_aug_assign))
    assert src.utils.astutils.var_contains_assign("x", ast.parse(simple_ann_assign))


def test_var_contains_assign_negative():
    assert not src.utils.astutils.var_contains_assign("y", ast.parse(simple_assign))
