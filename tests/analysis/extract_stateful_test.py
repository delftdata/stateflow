import pytest
from src.analysis.extract_class_descriptor import ExtractClassDescriptor
from src.descriptors import ClassDescriptor, MethodDescriptor
from src.analysis.extract_method_descriptor import ExtractMethodDescriptor
from typing import Any, Dict
import libcst as cst


def test_nested_class_negative():
    code = """
class Test:
    class Inner:
        pass
    """
    code_tree = cst.parse_module(code)
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "Test", expression_provider)

    with pytest.raises(AttributeError):
        code_tree.visit(visitor)


def test_class_name():
    code = """
class FancyClass:
    pass
    """
    code_tree = cst.parse_module(code)
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)

    code_tree.visit(visitor)

    clasz: ClassDescriptor = ExtractClassDescriptor.create_class_descriptor(visitor)
    assert clasz.class_name == "FancyClass"


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
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)

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
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)

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
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)

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
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)

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
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)

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
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)
    code_tree.visit(visitor)

    method = visitor.method_descriptors[1]
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
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)

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
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)

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
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)

    code_tree.visit(visitor)

    method = visitor.method_descriptors[1]
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
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)

    code_tree.visit(visitor)

    method = visitor.method_descriptors[1]
    assert method.read_only == True
    assert method.method_name == "fun"

    method = visitor.method_descriptors[2]
    assert method.read_only == False
    assert method.method_name == "fun_other"


def test_method_extraction_duplicate_methods():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self):
        x = 3
        y = self.x

    def fun(self, x):
        self.y = 2
    """

    code_tree = cst.parse_module(code)
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)

    code_tree.visit(visitor)

    method = visitor.method_descriptors[1]
    assert len(visitor.method_descriptors) == 2
    assert method.input_desc == {"x": "NoType"}


def test_method_extraction_no_self():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun_other():
        self.y = 2
    """

    code_tree = cst.parse_module(code)
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)

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
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)

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
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)

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
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)
    code_tree.visit(visitor)


def test_method_extraction_return_signature():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self) -> "Item":
        x = 3
        y = self.x
        """

    code_tree = cst.parse_module(code)

    # Get the function.
    fun_def: cst.FunctionDef = code_tree.body[0].body.body[1]

    visitor = ExtractMethodDescriptor(code_tree, fun_def)
    fun_def.visit(visitor)

    assert visitor.return_signature == ["Item"]


def test_method_extraction_return_signature():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self) -> Tuple[str, int, List[List[Dict[Any, str, "Item"]]], "Item"]:
        x = 3
        y = self.x
        """

    code_tree = cst.parse_module(code)

    # Get the function.
    fun_def: cst.FunctionDef = code_tree.body[0].body.body[1]

    visitor = ExtractMethodDescriptor(code_tree, fun_def)
    fun_def.visit(visitor)
    assert visitor.return_signature == [
        "str",
        "int",
        "List[List[Dict[Any, str, Item]]]",
        "Item",
    ]


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

    visitor = ExtractMethodDescriptor(code_tree, fun_def)
    with pytest.raises(AttributeError):
        fun_def.visit(visitor)


def test_method_extraction_typed_declarations():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4

    def fun(self):
        self.x = 3
        y: int = self.x
        return x
        """

    code_tree = cst.parse_module(code)

    # Get the function.
    fun_def: cst.FunctionDef = code_tree.body[0].body.body[1]

    visitor = ExtractMethodDescriptor(code_tree, fun_def)
    fun_def.visit(visitor)

    assert "y" in visitor.typed_declarations
    assert visitor.typed_declarations["y"] == "int"


def test_method_extraction_return_argument_extraction():
    code = """
class FancyClass:
    def __init__(self):
        self.x : int = 4
        self.z = 0

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
        
    def fun_5(self, x):
        y = x
        z = self.z
        return x, y, z
        """

    # Get the function.
    code_tree = cst.parse_module(code)
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)
    code_tree.visit(visitor)

    assert visitor.method_descriptors[1].output_desc.output_desc == [["NoType"]]
    assert "x" in visitor.method_descriptors[1].write_to_self_attributes
    assert "z" not in visitor.method_descriptors[1].write_to_self_attributes
    assert visitor.method_descriptors[2].output_desc.output_desc == [["int"]]
    assert visitor.method_descriptors[3].output_desc.output_desc == [
        ["str", "int", "List[int]"]
    ]
    assert visitor.method_descriptors[4].output_desc.output_desc == [
        ["str", "int", "List[int]"],
        ["str", "int", "List[int]"],
    ]
    assert visitor.method_descriptors[5].write_to_self_attributes == set()


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
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)

    with pytest.raises(AttributeError):
        code_tree.visit(visitor)


def test_only_analyze_decorated_class():
    code = """
class FancyClass:
    def __init__(self):
        pass

class OtherClass:
    pass
        """

    # Get the function.
    code_tree = cst.parse_module(code)
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)
    code_tree.visit(visitor)

    assert visitor.is_defined
    assert visitor.class_name == "FancyClass"


def test_correct_linking_other_classes():
    code = """
class FancyClass:
    def call(self, others: List["OtherClass"], str_list: List[str], other: "OtherClass"):
        pass

class OtherClass:
    def call(self, x: int):
        pass
            """

    # Get the function.
    code_tree = cst.parse_module(code)
    wrapper = cst.metadata.MetadataWrapper(code_tree)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    visitor_fancy = ExtractClassDescriptor(code_tree, "FancyClass", expression_provider)
    code_tree.visit(visitor_fancy)

    fancy: ClassDescriptor = ExtractClassDescriptor.create_class_descriptor(
        visitor_fancy
    )

    visitor_other = ExtractClassDescriptor(code_tree, "OtherClass", expression_provider)
    code_tree.visit(visitor_other)

    other: ClassDescriptor = ExtractClassDescriptor.create_class_descriptor(
        visitor_other
    )

    fancy.link_to_other_classes([fancy, other])
    other.link_to_other_classes([fancy, other])

    fancy_call: MethodDescriptor = fancy.get_method_by_name("call")
    assert fancy_call.other_class_links[0].class_name == "OtherClass"
    assert fancy_call._typed_declarations == {
        "others": "List[OtherClass]",
        "str_list": "List[str]",
        "other": "OtherClass",
    }
