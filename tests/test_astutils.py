import src.utils.astutils as astutils
import ast
import pytest

simple_assign = "x = 3"
simple_multiple_assign = "x, y = 3"
simple_aug_assign = "x += 3"
simple_ann_assign = "x: int = 3"

complex_assign = """
x = y
y + 3
z,x,b = y
b += y
return y
"""

complex_assign_two = """
x.y = 3

(complexExpression()).z = 4
"""


def test_var_contains_assign_positive():
    assert astutils.var_contains_assign("x", ast.parse(simple_assign))
    assert astutils.var_contains_assign("x", ast.parse(simple_multiple_assign))
    assert astutils.var_contains_assign("y", ast.parse(simple_multiple_assign))
    assert astutils.var_contains_assign("x", ast.parse(simple_aug_assign))
    assert astutils.var_contains_assign("x", ast.parse(simple_ann_assign))


def test_var_contains_assign_negative():
    assert not astutils.var_contains_assign("y", ast.parse(simple_assign))


def test_var_contains_assign_complex():
    assert astutils.var_contains_assign("x", ast.parse(complex_assign))
    assert astutils.var_contains_assign("b", ast.parse(complex_assign))
    assert astutils.var_contains_assign("z", ast.parse(complex_assign))
    assert astutils.var_contains_assign("x", ast.parse(complex_assign))
    assert not astutils.var_contains_assign("y", ast.parse(complex_assign))


def test_var_contains_assign_complex_two():
    assert not astutils.var_contains_assign("x", ast.parse(complex_assign_two))
    assert astutils.var_contains_assign("y", ast.parse(complex_assign_two))
    assert astutils.var_contains_assign("x.y", ast.parse(complex_assign_two))
    assert astutils.var_contains_assign("z", ast.parse(complex_assign_two))
    assert not astutils.var_contains_assign(
        "(complexExpression()).z", ast.parse(complex_assign_two)
    )
