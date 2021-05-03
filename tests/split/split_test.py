import pytest
from src.split.split import SplitAnalyzer, Split
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

    print(stmts[0].usages)
    print(stmts[1].dependencies)

    assert len(stmts) == 2
    assert stmts[0].dependencies == ["c", "d"]
    assert stmts[1].dependencies == ["d"]


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

    print(stmts[0].usages)
    print(stmts[1].dependencies)

    assert len(stmts) == 2
    assert stmts[0].dependencies == ["c", "d", "e"]
    assert stmts[1].dependencies == ["e", "g", "d"]


def test_dependencies_user_class():
    stateflow.clear()
    from tests.common.common_classes import User, Item

    wrapper = stateflow.registered_classes[1]
    method_desc = stateflow.registered_classes[1].class_desc.get_method_by_name(
        "buy_item"
    )

    print(wrapper)

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

    print(stmts[0].usages)
    print(stmts[1].dependencies)

    assert stmts[0].dependencies == ["amount", "item"]
    assert stmts[1].dependencies == ["total_price", "update_stock_return"]
