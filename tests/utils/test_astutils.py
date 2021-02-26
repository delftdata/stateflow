import astutils
import ast
import pytest

simple_assign = "x = 3"
simple_aug_assign = "x, y = 3"
simple_ann_assign = "x: int = 3"


def test_var_contains_assign_positive():
    print("HERE")
    assert astutils.var_contains_assign("y", ast.parse(simple_assign))
