import pytest
from src.analysis.extract_stateful_class import ExtractStatefulFun, StatefulFun
from src.analysis.extract_stateful_method import ExtractStatefulMethod
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
        self.i = r = 3
        self.q, no = 2
    
    def other_fun(self):
        self.x: int
        self.y: List[str]
        self.z = 3
        self.p += 3
        """
    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)

    code_tree.visit(visitor)

    merged_attributes: Dict[str, Any] = visitor.merge_self_attributes()
    final_dict = {
        "x": "int",
        "y": "List[str]",
        "z": "NoType",
        "p": "NoType",
        "i": "NoType",
        "q": "NoType",
    }

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


def test_async_func_error():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4
        self.x : str
        
    async def fun(self):
        pass
            """
    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)

    with pytest.raises(AttributeError):
        code_tree.visit(visitor)


def test_param_extraction_not_allow_default_values():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self, x: int = 3):
        pass
"""
    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)

    with pytest.raises(AttributeError):
        code_tree.visit(visitor)


def test_param_extraction_positive():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self, x: int, y: str, z):
        pass
    """

    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)
    code_tree.visit(visitor)

    method = visitor.method_descriptor[1]
    fun_params = {"x": "int", "y": "str", "z": "NoType"}
    assert method.input_desc == fun_params


def test_param_extraction_no_args():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self, *not_allowed):
        pass
    """

    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)

    with pytest.raises(AttributeError):
        code_tree.visit(visitor)


def test_param_extraction_no_kwargs():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self, **not_allowed):
        pass
    """

    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)

    with pytest.raises(AttributeError):
        code_tree.visit(visitor)


def test_param_extraction_no_arguments():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self):
        pass
    """

    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)

    code_tree.visit(visitor)

    method = visitor.method_descriptor[1]
    fun_params = {}
    assert method.input_desc == fun_params


def test_method_extraction_read_only():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self):
        x = 3
        y = self.x
        
    def fun_other(self):
        self.y = 2
    """

    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)

    code_tree.visit(visitor)

    method = visitor.method_descriptor[1]
    assert method.read_only == True

    method = visitor.method_descriptor[2]
    assert method.read_only == False


def test_method_extraction_no_self():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun_other():
        self.y = 2
    """

    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)

    with pytest.raises(AttributeError):
        code_tree.visit(visitor)


def test_method_extraction_attribute_error_call():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self):
        x = 3
        y = self.x

    def fun_other(self, item):
        item.buy(self.x)
    """

    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)

    with pytest.raises(AttributeError):
        code_tree.visit(visitor)


def test_method_extraction_attribute_error_access():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self):
        x = 3
        y = self.x

    def fun_other(self, item):
        item.buy = 4
    """

    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)

    with pytest.raises(AttributeError):
        code_tree.visit(visitor)


def test_method_extraction_attribute_no_error():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self):
        x = 3
        y = self.x

    def fun_other(self, item: Item):
        item.buy = 4
        item.call(self.x)
    """

    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)
    code_tree.visit(visitor)


def test_method_extraction_return_signature():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self) -> str:
        x = 3
        y = self.x
        """

    code_tree = cst.parse_module(code)

    # Get the function.
    fun_def: cst.FunctionDef = code_tree.body[0].body.body[1]

    visitor = ExtractStatefulMethod(code_tree, fun_def)
    fun_def.visit(visitor)

    assert visitor.return_signature == ["str"]


def test_method_extraction_return_signature():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self) -> Tuple[str, int, List[List[Dict[Any, str]]]]   :
        x = 3
        y = self.x
        """

    code_tree = cst.parse_module(code)

    # Get the function.
    fun_def: cst.FunctionDef = code_tree.body[0].body.body[1]

    visitor = ExtractStatefulMethod(code_tree, fun_def)
    fun_def.visit(visitor)
    assert visitor.return_signature == ["str", "int", "List[List[Dict[Any, str]]]"]


def test_method_extraction_return_no_call():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self):
        self.x = 3
        y = self.x
        return x.bye()
        """

    code_tree = cst.parse_module(code)

    # Get the function.
    fun_def: cst.FunctionDef = code_tree.body[0].body.body[1]

    visitor = ExtractStatefulMethod(code_tree, fun_def)
    with pytest.raises(AttributeError):
        fun_def.visit(visitor)


def test_method_extraction_return_argument_extraction():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self):
        self.x = 3
        y = self.x
        return x
        
    def fun_2(self) -> int:
        self.x = 3
        y = self.x
        return x

    def fun_3(self) -> Tuple[str, int, List[int]]:
        self.x = 3
        y = self.x
        return x, x, x
    
    def fun_4(self) -> Tuple[str, int, List[int]]:
        self.x = 3
        y = self.x
        if y:
            return y, y, y
        return x, x, x
        """

    # Get the function.
    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)
    code_tree.visit(visitor)

    assert visitor.method_descriptor[1].output_desc.output_desc == [["NoType"]]
    assert visitor.method_descriptor[2].output_desc.output_desc == [["int"]]
    assert visitor.method_descriptor[3].output_desc.output_desc == [
        ["str", "int", "List[int]"]
    ]
    assert visitor.method_descriptor[4].output_desc.output_desc == [
        ["str", "int", "List[int]"],
        ["str", "int", "List[int]"],
    ]


def test_method_extraction_return_len_mismatch():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self):
        self.x = 3
        y = self.x
        return x

    def fun_2(self) -> int:
        self.x = 3
        y = self.x
        return x, x
        """

    # Get the function.
    code_tree = cst.parse_module(code)
    visitor = ExtractStatefulFun(code_tree)

    with pytest.raises(AttributeError):
        code_tree.visit(visitor)
