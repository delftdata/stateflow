import pytest
from src.analysis.extract_stateful import ExtractStatefulFun, StatefulFun
from typing import Any, Dict
import libcst as cst


def test_nested_class_negative():
    code = """
class Test:
    class Inner:
        pass
    """
    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)

    with pytest.raises(AttributeError):
        code_tree.visit(visitor)


def test_class_name():
    code = """
class FancyClass:
    pass
    """
    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)

    code_tree.visit(visitor)

    statefun: StatefulFun = ExtractStatefulFun.create_stateful_fun(visitor)
    assert statefun.class_name == "FancyClass"


def test_merge_self_attributes_positive():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4
        self.x = self.no
        self.y: str
        self.z = self.z = 2
        """
    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)

    code_tree.visit(visitor)

    merged_attributes: Dict[str, Any] = visitor.merge_self_attributes()
    final_dict = {"x": "int", "y": "str", "z": "NoType"}

    assert merged_attributes == final_dict


def test_merge_self_attributes_multiple_fun_positive():
    code = """
class FancyClass:
    def __init__(self):
        self.x = 4
        self.x = self.no
    
    def other_fun(self):
        self.x: int
        self.y: List[str]
        self.z = 3
        """
    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)

    code_tree.visit(visitor)

    merged_attributes: Dict[str, Any] = visitor.merge_self_attributes()
    final_dict = {"x": "int", "y": "List[str]", "z": "NoType"}

    assert merged_attributes == final_dict


def test_merge_self_attributes_conflict():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4
        self.x : str
        """
    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)

    code_tree.visit(visitor)

    with pytest.raises(AttributeError):
        visitor.merge_self_attributes()
