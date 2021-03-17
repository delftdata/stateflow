import pytest
from src.analysis.extract_stateful import ExtractStatefulFun, StatefulFun

import libcst as cst


def test_nested_class_negative():
    code = """
class Test:
    class Inner:
        pass
    """
    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun()

    with pytest.raises(AttributeError):
        code_tree.visit(visitor)


def test_class_name():
    code = """
class FancyClass:
    pass
    """
    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun()

    code_tree.visit(visitor)

    statefun: StatefulFun = ExtractStatefulFun.create_stateful_fun(visitor)
    assert statefun.class_name == "FancyClass"
