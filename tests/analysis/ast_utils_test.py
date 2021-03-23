import pytest
import libcst as cst
from src.analysis.ast_utils import *


def test_self_positive():
    stmt = "self.x"
    parsed = cst.parse_statement(stmt)

    assert is_self(parsed.body[0].value)


def test_self_negative():
    stmt = "not_self.x"
    parsed = cst.parse_statement(stmt)

    assert not is_self(parsed.body[0].value)


def test_self_not_attribute():
    stmt = "x + 3"
    parsed = cst.parse_statement(stmt)

    assert not is_self(parsed.body[0].value)
