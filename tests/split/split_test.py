import pytest
from src.split.split_analyze import (
    SplitAnalyzer,
    Split,
    RemoveAfterClassDefinition,
    SplitTransformer,
)
import src.stateflow as stateflow


def test_split_dependencies():
    stateflow.clear()

    class B:
        def __init__(self):
            self.a = 0

        def get_a(self):
            return self.a

    class A:
        def __init__(self):
            self.a = 0
            self.b = 0

        def get_a(self, b: B, c: int, d: int):
            a = 3
            d = c + 1 + a + d
            b_new = b.get_a()
            return self.a + b_new + d

    stateflow.stateflow(B, parse_file=False)
    stateflow.stateflow(A, parse_file=False)

    a_wrapper = stateflow.registered_classes[1]
    a_method_desc = stateflow.registered_classes[1].class_desc.get_method_by_name(
        "get_a"
    )

    split = Split(
        [cls.class_desc for cls in stateflow.registered_classes],
        stateflow.registered_classes,
    )

    analyzer = SplitAnalyzer(
        split,
        a_wrapper.class_desc.class_node,
        a_method_desc.method_node,
        a_method_desc,
        a_wrapper.class_desc.expression_provider,
    )
    stmts = analyzer.parsed_statements

    assert len(stmts) == 2
    assert stmts[0].dependencies == ["c", "d"]
    assert stmts[1].dependencies == ["d", "get_a_return"]


def test_split_dependencies_more():
    stateflow.clear()

    class C:
        def __init__(self):
            self.a = 0

        def get_a(self):
            return self.a

    class D:
        def __init__(self):
            self.a = 0
            self.b = 0

        def get_a(self, b: C, c: int, d: int, e: int):
            a = 3
            d = e = g = c + 1 + a + d + e
            b_new = b.get_a() + e + g
            return self.a + b_new + d

    stateflow.stateflow(C, parse_file=False)
    stateflow.stateflow(D, parse_file=False)

    a_wrapper = stateflow.registered_classes[1]
    a_method_desc = stateflow.registered_classes[1].class_desc.get_method_by_name(
        "get_a"
    )

    split = Split(
        [cls.class_desc for cls in stateflow.registered_classes],
        stateflow.registered_classes,
    )

    analyzer = SplitAnalyzer(
        split,
        a_wrapper.class_desc.class_node,
        a_method_desc.method_node,
        a_method_desc,
        a_wrapper.class_desc.expression_provider,
    )
    stmts = analyzer.parsed_statements

    assert len(stmts) == 2
    assert stmts[0].dependencies == ["c", "d", "e"]
    assert stmts[1].dependencies == ["e", "g", "d", "get_a_return"]


def test_dependencies_user_class():
    stateflow.clear()
    from tests.common.common_classes import User, Item

    stateflow.stateflow(Item, parse_file=False)
    stateflow.stateflow(User, parse_file=False)

    wrapper = stateflow.registered_classes[1]
    method_desc = stateflow.registered_classes[1].class_desc.get_method_by_name(
        "buy_item"
    )

    split = Split(
        [cls.class_desc for cls in stateflow.registered_classes],
        stateflow.registered_classes,
    )

    analyzer = SplitAnalyzer(
        split,
        wrapper.class_desc.class_node,
        method_desc.method_node,
        method_desc,
        wrapper.class_desc.expression_provider,
    )
    stmts = analyzer.parsed_statements

    assert stmts[0].dependencies == ["amount", "item"]
    assert stmts[1].dependencies == ["total_price", "update_stock_return"]


def test_multiple_splits():
    stateflow.clear()

    class CC(object):
        def __init__(self):
            self.x = 0

        def set(self, x: int):
            self.x = x
            return self.a

    class BB(object):
        def __init__(self):
            self.a = 0

        def get(self, a: int):
            return self.a + a

    class AA(object):
        def __init__(self):
            self.a = 0
            self.b = 0

        def cool_method(self, b: BB, c: CC):
            a = self.a + self.b

            b_result = b.get(a * 9)
            new_a = b_result * a

            c_result = c.set(new_a)

            return c_result + b_result + a

    stateflow.stateflow(AA, parse_file=False)
    stateflow.stateflow(BB, parse_file=False)
    stateflow.stateflow(CC, parse_file=False)

    wrapper = stateflow.registered_classes[0]
    method_desc = stateflow.registered_classes[0].class_desc.get_method_by_name(
        "cool_method"
    )

    print(
        [
            method.method_name
            for m in stateflow.registered_classes
            for method in m.class_desc.methods_dec
        ]
    )

    split = Split(
        [cls.class_desc for cls in stateflow.registered_classes],
        stateflow.registered_classes,
    )

    analyzer = SplitAnalyzer(
        split,
        wrapper.class_desc.class_node,
        method_desc.method_node,
        method_desc,
        wrapper.class_desc.expression_provider,
    )
    stmts = analyzer.parsed_statements

    # We have 3 statement blocks.
    assert len(stmts) == 3

    # We check the dependencies and definitions of the blocks.
    assert stmts[0].dependencies == []
    assert stmts[0].definitions == ["a", "b", "c"]

    remove_after_class_def = RemoveAfterClassDefinition(wrapper.class_desc.class_name)

    modified_tree = wrapper.class_desc.module_node.visit(remove_after_class_def)

    methods = {"cool_method": stmts}

    modified_tree = modified_tree.visit(
        SplitTransformer(wrapper.class_desc.class_name, methods)
    )

    print(modified_tree.code)

    print("--")
    print(stmts[0].dependencies)
    print(stmts[1].dependencies)
    print(stmts[2].dependencies)
    print("---")
    print(stmts[0].definitions)
    print(stmts[1].definitions)
    print(stmts[2].definitions)
    assert stmts[1].dependencies == ["a", "get_return"]
    assert stmts[1].definitions == ["b_result", "new_a"]

    assert stmts[2].dependencies == ["b_result", "a", "set_return"]
    assert stmts[2].definitions == ["c_result"]
