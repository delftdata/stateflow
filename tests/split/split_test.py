import pytest
from tests.context import stateflow
from stateflow.split.split_analyze import (
    SplitAnalyzer,
    Split,
    RemoveAfterClassDefinition,
    SplitTransformer,
    SplitContext,
    Block,
    StatementBlock,
    ConditionalBlock,
)
from stateflow.dataflow.event_flow import (
    StartNode,
    InvokeExternal,
    InvokeSplitFun,
    ReturnNode,
    RequestState,
    InvokeConditional,
    InvokeFor,
)
from typing import List
import stateflow as stateflow


def test_split_dependencies():
    stateflow.core.clear()

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
            a: B = 3
            d = c + 1 + a + d
            b_new = b.get_a()
            return self.a + b_new + d

    stateflow.stateflow(B, parse_file=False)
    stateflow.stateflow(A, parse_file=False)

    a_wrapper = stateflow.core.registered_classes[1]
    a_method_desc = stateflow.core.registered_classes[1].class_desc.get_method_by_name(
        "get_a"
    )

    split = Split(
        [cls.class_desc for cls in stateflow.core.registered_classes],
        stateflow.core.registered_classes,
    )

    analyzer = SplitAnalyzer(
        a_wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            a_wrapper.class_desc.expression_provider,
            a_method_desc.method_node,
            a_method_desc,
            stateflow.core.registered_classes[0].class_desc,
        ),
        a_method_desc.method_node.body.children,
    )
    stmts = analyzer.blocks

    from stateflow.util.dataflow_visualizer import visualize

    visualize(stmts, code=True)

    assert len(stmts) == 2
    assert stmts[0].dependencies == ["c", "d", "b"]
    assert stmts[1].dependencies == ["d", "get_a_return"]


def test_split_dependencies_more():
    stateflow.core.clear()

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

    a_wrapper = stateflow.core.registered_classes[1]
    a_method_desc = stateflow.core.registered_classes[1].class_desc.get_method_by_name(
        "get_a"
    )

    split = Split(
        [cls.class_desc for cls in stateflow.core.registered_classes],
        stateflow.core.registered_classes,
    )

    analyzer = SplitAnalyzer(
        a_wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            a_wrapper.class_desc.expression_provider,
            a_method_desc.method_node,
            a_method_desc,
            stateflow.core.registered_classes[0].class_desc,
        ),
        a_method_desc.method_node.body.children,
    )
    stmts = analyzer.blocks

    assert len(stmts) == 2
    assert stmts[0].dependencies == ["c", "d", "e", "b"]
    assert stmts[1].dependencies == ["e", "g", "d", "get_a_return"]


def test_dependencies_user_class():
    stateflow.core.clear()
    from tests.common.common_classes import User, Item

    stateflow.stateflow(Item, parse_file=False)
    stateflow.stateflow(User, parse_file=False)

    wrapper = stateflow.core.registered_classes[1]
    method_desc = stateflow.core.registered_classes[1].class_desc.get_method_by_name(
        "buy_item"
    )

    split = Split(
        [cls.class_desc for cls in stateflow.core.registered_classes],
        stateflow.core.registered_classes,
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.core.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )
    stmts = analyzer.blocks

    for stmt in stmts:
        print(stmt.code())

    assert stmts[0].dependencies == ["amount", "item"]
    assert stmts[1].dependencies == ["total_price"]
    assert stmts[2].dependencies == []
    assert stmts[3].dependencies == []
    assert stmts[4].dependencies == ["amount", "item"]
    assert stmts[5].dependencies == ["update_stock_return"]
    assert stmts[6].dependencies == []
    assert stmts[7].dependencies == ["total_price"]


def test_multiple_splits():
    stateflow.core.clear()

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
            a = self.a + self.b + b.a + c.x

            b_result = b.get(a * 9)
            new_a = b_result * a

            c_result = c.set(new_a)

            return c_result + b_result + a

    stateflow.stateflow(AA, parse_file=False)
    stateflow.stateflow(BB, parse_file=False)
    stateflow.stateflow(CC, parse_file=False)

    wrapper = stateflow.core.registered_classes[0]
    method_desc = stateflow.core.registered_classes[0].class_desc.get_method_by_name(
        "cool_method"
    )

    print(
        [
            method.method_name
            for m in stateflow.core.registered_classes
            for method in m.class_desc.methods_dec
        ]
    )

    split = Split(
        [cls.class_desc for cls in stateflow.core.registered_classes],
        stateflow.core.registered_classes,
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.core.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )
    stmts = analyzer.blocks

    # We have 3 statement blocks.
    assert len(stmts) == 3

    # We check the dependencies and definitions of the blocks.
    assert stmts[0].dependencies == ["b", "c"]
    assert stmts[0].definitions == ["a", "b", "c"]

    remove_after_class_def = RemoveAfterClassDefinition(wrapper.class_desc.class_name)

    modified_tree = wrapper.class_desc.module_node.visit(remove_after_class_def)

    methods = {"cool_method": stmts}

    modified_tree = modified_tree.visit(
        SplitTransformer(wrapper.class_desc.class_name, methods)
    )

    print(modified_tree.code)
    assert stmts[1].dependencies == ["a", "c", "get_return"]
    assert stmts[1].definitions == ["b_result", "new_a"]

    assert stmts[2].dependencies == ["b_result", "a", "set_return"]
    assert stmts[2].definitions == ["c_result"]

    # INVOKE SPLIT FUN -> INVOKE EXTERNAL
    node_one = stmts[0].build_event_flow_nodes(0)

    assert len(node_one) == 4

    assert node_one[0].id == 1 and isinstance(node_one[0], RequestState)
    assert node_one[0].next == [node_one[1].id]
    assert node_one[0].var_name == "b"
    assert node_one[0].fun_addr.function_type.name == "BB"

    assert node_one[1].id == 2 and isinstance(node_one[1], RequestState)
    assert node_one[1].previous == node_one[0].id
    assert node_one[1].next == [node_one[2].id]
    assert node_one[1].var_name == "c"
    assert node_one[1].fun_addr.function_type.name == "CC"

    assert node_one[2].id == 3 and isinstance(node_one[2], InvokeSplitFun)
    assert node_one[2].previous == node_one[1].id
    assert node_one[2].next == [node_one[3].id]
    assert node_one[2].fun_addr.function_type.name == "AA"

    assert node_one[3].id == 4 and isinstance(node_one[3], InvokeExternal)
    assert node_one[3].previous == node_one[2].id
    assert node_one[3].next == []
    assert node_one[3].fun_addr.function_type.name == "BB"

    node_last = stmts[-1].build_event_flow_nodes(0)
    assert len(node_last) == 2
    assert node_last[0].id == 1 and isinstance(node_last[0], InvokeSplitFun)
    assert node_last[0].fun_addr.function_type.name == "AA"

    assert node_last[1].id == 2 and isinstance(node_last[1], ReturnNode)
    assert node_last[1].previous == node_last[0].id

    node_inter = stmts[1].build_event_flow_nodes(0)
    assert len(node_inter) == 2
    assert node_inter[0].id == 1 and isinstance(node_inter[0], InvokeSplitFun)
    assert node_inter[0].fun_addr.function_type.name == "AA"
    assert node_inter[1].id == 2 and isinstance(node_inter[1], InvokeExternal)
    assert node_inter[1].fun_addr.function_type.name == "CC"


def test_multiple_splits_with_returns():
    stateflow.core.clear()

    class CCC(object):
        def __init__(self):
            self.x = 0

        def set(self, x: int):
            self.x = x
            return self.a

    class BBB(object):
        def __init__(self):
            self.a = 0

        def get(self, a: int):
            return self.a + a

    class AAA(object):
        def __init__(self):
            self.a = 0
            self.b = 0

        def cool_method(self, b: BBB, c: CCC):
            a = self.a + self.b + b.a + c.x

            if a > 10:
                return a

            b_result = b.get(a * 9)
            new_a = b_result * a

            if new_a > 10:
                return self.a

            c_result = c.set(new_a)

            return c_result + b_result + a

    stateflow.stateflow(AAA, parse_file=False)
    stateflow.stateflow(BBB, parse_file=False)
    stateflow.stateflow(CCC, parse_file=False)

    wrapper = stateflow.core.registered_classes[0]
    method_desc = stateflow.core.registered_classes[0].class_desc.get_method_by_name(
        "cool_method"
    )

    print(
        [
            method.method_name
            for m in stateflow.core.registered_classes
            for method in m.class_desc.methods_dec
        ]
    )

    split = Split(
        [cls.class_desc for cls in stateflow.core.registered_classes],
        stateflow.core.registered_classes,
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.core.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )
    stmts = analyzer.blocks

    # GET STATE -> GET STATE -> INVOKE SPLIT FUN -> INVOKE EXTERNAL
    node_one = stmts[0].build_event_flow_nodes(0)

    from stateflow.util import dataflow_visualizer

    dataflow_visualizer.visualize_flow(node_one)
    dataflow_visualizer.visualize(stmts, code=True)
    print(stmts[0].code())
    print(stmts[1].code())

    assert len(node_one) == 3

    assert node_one[0].id == 1 and isinstance(node_one[0], RequestState)
    assert node_one[0].var_name == "b"
    assert node_one[0].fun_addr.function_type.name == "BBB"

    assert node_one[1].id == 2 and isinstance(node_one[1], RequestState)
    assert node_one[1].var_name == "c"
    assert node_one[1].fun_addr.function_type.name == "CCC"

    assert node_one[2].id == 3 and isinstance(node_one[2], InvokeSplitFun)
    assert node_one[2].fun_addr.function_type.name == "AAA"

    node_two = stmts[1].build_event_flow_nodes(len(node_one))
    assert node_two[0].id == 4 and isinstance(node_two[0], InvokeConditional)

    node_three = stmts[2].build_event_flow_nodes(len(node_one) + len(node_two))
    assert node_three[0].id == 5 and isinstance(node_three[0], InvokeSplitFun)
    assert node_three[1].id == 6 and isinstance(node_three[1], ReturnNode)

    node_four = stmts[3].build_event_flow_nodes(
        len(node_one) + len(node_two) + len(node_three)
    )
    assert node_four[0].id == 7 and isinstance(node_four[0], InvokeSplitFun)
    assert (
        node_four[1].id == 8
        and isinstance(node_four[1], InvokeExternal)
        and node_four[1].fun_addr.function_type.name == "BBB"
    )

    node_five = stmts[4].build_event_flow_nodes(
        len(node_one) + len(node_two) + len(node_three) + len(node_four)
    )

    assert node_five[0].id == 9 and isinstance(node_five[0], InvokeSplitFun)

    node_six = stmts[5].build_event_flow_nodes(
        len(node_one)
        + len(node_two)
        + len(node_three)
        + len(node_four)
        + len(node_five)
    )

    assert node_six[0].id == 10 and isinstance(node_six[0], InvokeConditional)

    node_seven = stmts[6].build_event_flow_nodes(
        len(node_one)
        + len(node_two)
        + len(node_three)
        + len(node_four)
        + len(node_five)
        + len(node_six)
    )
    assert node_seven[0].id == 11 and isinstance(node_seven[0], InvokeSplitFun)
    assert node_seven[1].id == 12 and isinstance(node_seven[1], ReturnNode)

    node_eight = stmts[7].build_event_flow_nodes(
        len(node_one)
        + len(node_two)
        + len(node_three)
        + len(node_four)
        + len(node_five)
        + len(node_six)
        + len(node_seven)
    )
    assert node_eight[0].id == 13 and isinstance(node_eight[0], InvokeSplitFun)
    assert node_eight[1].id == 14 and isinstance(node_eight[1], InvokeExternal)

    node_nine = stmts[8].build_event_flow_nodes(
        len(node_one)
        + len(node_two)
        + len(node_three)
        + len(node_four)
        + len(node_five)
        + len(node_six)
        + len(node_seven)
        + len(node_eight)
    )
    assert node_nine[0].id == 15 and isinstance(node_nine[0], InvokeSplitFun)
    assert node_nine[1].id == 16 and isinstance(node_nine[1], ReturnNode)


def test_if_statements():
    stateflow.core.clear()

    class Other(object):
        def __init__(self):
            self.x = 0

        def set(self, x: int):
            self.x = x
            return self.a

        def bigger_than(self, x: int) -> bool:
            return x > self.x

    class IfClass(object):
        def __init__(self):
            self.a = 0
            self.b = 0

        def cool_method(self, other: Other):
            a = self.a + self.b
            if a > 3:
                other.set(self.a * 9)
            elif other.bigger_than(self.a):
                self.a = 5
                hoi = 4
            else:
                other.set(self.b)

            return self.b

    stateflow.stateflow(IfClass, parse_file=False)
    stateflow.stateflow(Other, parse_file=False)

    wrapper = stateflow.core.registered_classes[0]
    method_desc = stateflow.core.registered_classes[0].class_desc.get_method_by_name(
        "cool_method"
    )

    split = Split(
        [cls.class_desc for cls in stateflow.core.registered_classes],
        stateflow.core.registered_classes,
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.core.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )

    blocks: List[Block] = analyzer.blocks

    from stateflow.util import dataflow_visualizer

    dataflow_visualizer.visualize(blocks)

    # Check unique id's
    assert len([b.block_id for b in blocks]) == len(set([b.block_id for b in blocks]))

    """ block 0
    a = self.a + self.b
    """
    assert isinstance(blocks[0], StatementBlock)
    assert blocks[0].dependencies == [
        "other"
    ]  # Actually it has dependencies, but those are in the parameters we assume.
    assert blocks[0].definitions == ["a", "other"]  # We add parameters as definitions.
    assert blocks[0].previous_block is None
    assert blocks[0].next_block == [blocks[1]]

    print(blocks[0].code())

    # Block 1
    # if a > 3:
    assert isinstance(blocks[1], ConditionalBlock)
    assert blocks[1].dependencies == ["a"]
    assert blocks[1].previous_block == blocks[0]
    assert set(blocks[1].next_block) == set([blocks[2], blocks[4]])
    assert blocks[1].invocation_block == None
    assert blocks[1].true_block == blocks[2]
    assert blocks[1].false_block == blocks[4]

    """ block 2
    other.set(self.a)
    
    which is split again in two 2 blocks:
    - invoke_set_arg_x = self.a * 9 and returns a InvokeMethodRequest
    - set_return
    """
    # invoke_set_arg_x = self.a * 9
    assert isinstance(blocks[2], StatementBlock)
    assert blocks[2].dependencies == ["other"]
    assert (
        blocks[2].definitions == []
    )  # Assignments for methods are not seen as definitions, because they are wrapped.
    assert blocks[2].previous_block == blocks[1]
    assert blocks[2].next_block == [blocks[3]]

    # Block 3
    # set_return
    print(f"{[b.block_id for b in blocks[3].next_block]}")
    assert isinstance(blocks[3], StatementBlock)
    assert blocks[3].dependencies == ["set_return"]
    assert blocks[3].definitions == []
    assert blocks[3].previous_block == blocks[2]
    assert blocks[3].next_block == [blocks[9]]

    # Block 4
    # invoke_bigger_than_x = self.a
    assert isinstance(blocks[4], StatementBlock)
    assert blocks[4].dependencies == ["other"]
    assert blocks[4].definitions == []
    assert blocks[4].previous_block == blocks[1]
    assert blocks[4].next_block == [blocks[5]]

    # bigger_than_result
    assert isinstance(blocks[5], ConditionalBlock)
    assert blocks[5].dependencies == ["bigger_than_return"]
    assert blocks[5].definitions == []
    assert blocks[5].previous_block == blocks[4]
    assert blocks[5].invocation_block == blocks[4]
    assert blocks[5].next_block == [blocks[6], blocks[7]]
    assert blocks[5].true_block == blocks[6]
    assert blocks[5].false_block == blocks[7]

    # self.a = 5
    assert isinstance(blocks[6], StatementBlock)
    assert blocks[6].dependencies == []
    assert blocks[6].definitions == ["hoi"]
    assert blocks[6].previous_block == blocks[5]
    assert blocks[6].next_block == [blocks[9]]

    # else
    assert isinstance(blocks[7], StatementBlock)
    assert blocks[7].dependencies == ["other"]
    assert blocks[7].definitions == []
    assert blocks[7].previous_block == blocks[5]
    assert blocks[7].next_block == [blocks[8]]

    # other.set(self.b)
    assert isinstance(blocks[8], StatementBlock)
    assert blocks[8].dependencies == ["set_return"]
    assert blocks[8].definitions == []
    assert blocks[8].previous_block == blocks[7]
    assert blocks[8].next_block == [blocks[9]]

    # return other.x
    assert isinstance(blocks[9], StatementBlock)

    method_desc.split_function(
        blocks, wrapper.class_desc.to_function_type().to_address()
    )
    dataflow_visualizer.visualize(blocks, True)
    dataflow_visualizer.visualize_flow(method_desc.flow_list)


def test_if_non_split():
    stateflow.core.clear()

    class DummyIf:
        def __init__(self):
            pass

        def invoke(self):
            return True

    class IfNoSplit(object):
        def __init__(self):
            self.x = 0

        def invoke(self, x: int, d: DummyIf) -> bool:
            self.x = x
            if x > 3:
                x = 5 * 3
                return True
            elif x < 3:
                x = 4
            else:
                x = 6
                return False

            d.invoke()

            return x > self.x

    stateflow.stateflow(IfNoSplit, parse_file=False)
    stateflow.stateflow(DummyIf, parse_file=False)

    wrapper = stateflow.core.registered_classes[0]
    method_desc = stateflow.core.registered_classes[0].class_desc.get_method_by_name(
        "invoke"
    )
    split = Split(
        [cls.class_desc for cls in stateflow.core.registered_classes],
        stateflow.core.registered_classes,
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.core.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )

    blocks: List[Block] = analyzer.blocks

    from stateflow.util import dataflow_visualizer

    dataflow_visualizer.visualize(blocks, True)

    method_desc.split_function(
        blocks, wrapper.class_desc.to_function_type().to_address()
    )

    dataflow_visualizer.visualize_flow(method_desc.flow_list)


def test_if_statements_complex():
    stateflow.core.clear()

    class OtherComplex(object):
        def __init__(self):
            self.x = 0

        def set(self, x: int):
            self.x = x
            return self.a

        def bigger_than(self, x: int) -> bool:
            return x > self.x

    class IfClassComplex(object):
        def __init__(self):
            self.a = 0
            self.b = 0

        def cool_method(self, other: OtherComplex):
            if self.a > 3:
                if self.b < 0:
                    return
                else:
                    other.set(self.b)
            else:
                other.set(self.a)

            return other.x

    stateflow.stateflow(IfClassComplex, parse_file=False)
    stateflow.stateflow(OtherComplex, parse_file=False)

    wrapper = stateflow.core.registered_classes[0]
    method_desc = stateflow.core.registered_classes[0].class_desc.get_method_by_name(
        "cool_method"
    )

    split = Split(
        [cls.class_desc for cls in stateflow.core.registered_classes],
        stateflow.core.registered_classes,
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.core.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )

    blocks: List[Block] = analyzer.blocks

    from stateflow.util import dataflow_visualizer

    dataflow_visualizer.visualize(blocks, True)
    method_desc.split_function(
        blocks, wrapper.class_desc.to_function_type().to_address()
    )
    dataflow_visualizer.visualize_flow(method_desc.flow_list)


def test_list_items():
    stateflow.core.clear()

    class ListOtherClass(object):
        def __init__(self):
            self.x = 0

        def set(self, x: int):
            self.x = x
            return self.a

        def bigger_than(self, x: int) -> bool:
            return x > self.x

    class ListClass(object):
        def __init__(self):
            self.a = 0
            self.b = 0

        def cool_method(self, others: List[ListOtherClass]):
            first_item: ListOtherClass = others[0]
            first_item.set(self.a * 3)

            if self.b == 0:
                others[-1].set(self.b)

    stateflow.stateflow(ListClass, parse_file=False)
    stateflow.stateflow(ListOtherClass, parse_file=False)

    wrapper = stateflow.core.registered_classes[0]
    method_desc = stateflow.core.registered_classes[0].class_desc.get_method_by_name(
        "cool_method"
    )

    split = Split(
        [cls.class_desc for cls in stateflow.core.registered_classes],
        stateflow.core.registered_classes,
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.core.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )

    blocks: List[Block] = analyzer.blocks

    # from util import dataflow_visualizer
    #
    # dataflow_visualizer.visualize(blocks, True)
    # method_desc.split_function(blocks)
    # dataflow_visualizer.visualize_flow(method_desc.flow_list)

    assert len(blocks) == 6


def test_request_state():
    stateflow.core.clear()

    class StateClass:
        def __init__(self):
            self.x = 5
            self.y = 5

        def dummy_call(self):
            return

        def invalidate(self):
            self.x = 0

        def request_state_simple(self, state: "StateClass"):  # noqa: F821
            x1 = state.x
            state.dummy_call()
            x2 = state.x

        def request_state_simple_invalidate(self, state: "StateClass"):  # noqa: F821
            x1 = state.x
            state.invalidate()
            x2 = state.x

        def request_state_invalidate(self, state: "StateClass"):  # noqa: F821
            x1 = state.x
            if x1 > 0:
                if x1 > 1:
                    print(x1)
                elif state.invalidate():
                    x2 = state.x
            else:
                x2 = 3

            x3 = state.x

        def request_state_invalidate_2(self, state: "StateClass"):  # noqa: F821
            x1 = state.x
            state.invalidate()

            for x in range(0, 10):
                print(x)

            if x > 3:
                print(x)
            else:
                print(x)

            x3 = state.x

        def request_state_not_invalidate(self, state: "StateClass"):  # noqa: F821
            x1 = state.x
            state.dummy_call()

            for x in range(0, 10):
                print(x)

            if x > 3:
                print(x)
            else:
                if x > 4:
                    state.x
                print(x)

            x3 = state.x

        def request_for(self, state: List["StateClass"]):  # noqa: F821
            y: "StateClass" = state[0]
            x1 = y.x
            y.invalidate()
            for x in state:
                print(x.x)
                x.dummy_call()

            x2 = y.x

        def request_rename(self, state: List["StateClass"]):  # noqa: F821
            x: StateClass = state[0]
            y: StateClass = x
            x.x
            y.invalidate()
            x.x

    stateflow.stateflow(StateClass, parse_file=False)
    wrapper = stateflow.core.registered_classes[0]
    method_desc = stateflow.core.registered_classes[0].class_desc.get_method_by_name(
        "request_state_simple"
    )

    split = Split(
        [cls.class_desc for cls in stateflow.core.registered_classes],
        stateflow.core.registered_classes,
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.core.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )

    blocks: List[Block] = analyzer.blocks

    from stateflow.util import dataflow_visualizer

    dataflow_visualizer.visualize(blocks, True)
    method_desc.split_function(
        blocks, wrapper.class_desc.to_function_type().to_address()
    )
    dataflow_visualizer.visualize_flow(method_desc.flow_list)

    flow = method_desc.flow_list
    request_blocks = [block for block in flow if isinstance(block, RequestState)]
    assert len(flow) == 6
    assert isinstance(flow[1], RequestState)
    assert flow[1].var_name == "state"
    assert flow[1].fun_addr.function_type.name == "StateClass"
    assert len(request_blocks) == 1

    method_desc = stateflow.core.registered_classes[0].class_desc.get_method_by_name(
        "request_state_invalidate"
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.core.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )

    blocks: List[Block] = analyzer.blocks
    dataflow_visualizer.visualize(blocks, True)
    method_desc.split_function(
        blocks, wrapper.class_desc.to_function_type().to_address()
    )
    dataflow_visualizer.visualize_flow(method_desc.flow_list)

    flow = method_desc.flow_list
    request_blocks = [block for block in flow if isinstance(block, RequestState)]
    assert len(request_blocks) == 3
    assert isinstance(flow[1], RequestState)
    assert flow[1].var_name == "state"

    assert isinstance(flow[10], RequestState)
    assert flow[10].var_name == "state"

    assert isinstance(flow[14], RequestState)
    assert flow[14].var_name == "state"

    method_desc = stateflow.core.registered_classes[0].class_desc.get_method_by_name(
        "request_state_invalidate_2"
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.core.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )

    blocks: List[Block] = analyzer.blocks
    dataflow_visualizer.visualize(blocks, True)
    method_desc.split_function(
        blocks, wrapper.class_desc.to_function_type().to_address()
    )
    dataflow_visualizer.visualize_flow(method_desc.flow_list)

    flow = method_desc.flow_list
    request_blocks = [block for block in flow if isinstance(block, RequestState)]
    assert len(request_blocks) == 2
    assert isinstance(flow[1], RequestState)
    assert flow[1].var_name == "state"

    assert isinstance(flow[11], RequestState)
    assert flow[11].var_name == "state"

    method_desc = stateflow.core.registered_classes[0].class_desc.get_method_by_name(
        "request_state_not_invalidate"
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.core.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )

    blocks: List[Block] = analyzer.blocks
    dataflow_visualizer.visualize(blocks, True)
    method_desc.split_function(
        blocks, wrapper.class_desc.to_function_type().to_address()
    )
    dataflow_visualizer.visualize_flow(method_desc.flow_list)

    flow = method_desc.flow_list
    request_blocks = [block for block in flow if isinstance(block, RequestState)]
    assert len(request_blocks) == 1
    assert isinstance(flow[1], RequestState)
    assert flow[1].var_name == "state"

    method_desc = stateflow.core.registered_classes[0].class_desc.get_method_by_name(
        "request_for"
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.core.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )

    blocks: List[Block] = analyzer.blocks
    dataflow_visualizer.visualize(blocks, True)
    method_desc.split_function(
        blocks, wrapper.class_desc.to_function_type().to_address()
    )
    dataflow_visualizer.visualize_flow(method_desc.flow_list)

    flow = method_desc.flow_list
    request_blocks = [block for block in flow if isinstance(block, RequestState)]
    assert len(request_blocks) == 3

    assert request_blocks[0].id == 2
    assert request_blocks[0].var_name == "y"
    assert request_blocks[1].id == 7
    assert request_blocks[1].var_name == "x"
    assert request_blocks[2].id == 11
    assert request_blocks[2].var_name == "y"

    method_desc = stateflow.core.registered_classes[0].class_desc.get_method_by_name(
        "request_state_simple_invalidate"
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.core.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )

    blocks: List[Block] = analyzer.blocks
    dataflow_visualizer.visualize(blocks, True)
    method_desc.split_function(
        blocks, wrapper.class_desc.to_function_type().to_address()
    )
    dataflow_visualizer.visualize_flow(method_desc.flow_list)

    flow = method_desc.flow_list
    request_blocks = [block for block in flow if isinstance(block, RequestState)]
    assert len(request_blocks) == 2

    method_desc = stateflow.core.registered_classes[0].class_desc.get_method_by_name(
        "request_rename"
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.core.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )

    blocks: List[Block] = analyzer.blocks
    dataflow_visualizer.visualize(blocks, True)
    method_desc.split_function(
        blocks, wrapper.class_desc.to_function_type().to_address()
    )
    dataflow_visualizer.visualize_flow(method_desc.flow_list)

    flow = method_desc.flow_list
    request_blocks = [block for block in flow if isinstance(block, RequestState)]
    assert len(request_blocks) == 2
    assert request_blocks[0].id == 2
    assert request_blocks[1].id == 5


# def test_if_no_false():
#     stateflow.core.clear()
#
#     class NoFalseBlock(object):
#         def __init__(self):
#             self.x = 0
#
#         def execute(self, x: int):
#             if True:
#                 if True:
#                     return x
#
#     stateflow.stateflow(NoFalseBlock, parse_file=False)
#
#     wrapper = stateflow.core.registered_classes[0]
#     method_desc = stateflow.core.registered_classes[0].class_desc.get_method_by_name(
#         "execute"
#     )
#
#     split = Split(
#         [cls.class_desc for cls in stateflow.core.registered_classes],
#         stateflow.core.registered_classes,
#     )
#
#     analyzer = SplitAnalyzer(
#         wrapper.class_desc.class_node,
#         SplitContext(
#             split.name_to_descriptor,
#             wrapper.class_desc.expression_provider,
#             method_desc.method_node,
#             method_desc,
#             stateflow.core.registered_classes[0].class_desc,
#         ),
#         method_desc.method_node.body.children,
#     )
#
#     blocks: List[Block] = analyzer.blocks
#
#     from stateflow.util import dataflow_visualizer
#
#     print(dataflow_visualizer.visualize(blocks, True))
#     method_desc.split_function(
#         blocks, wrapper.class_desc.to_function_type().to_address()
#     )
#     print(dataflow_visualizer.visualize_flow(method_desc.flow_list))


def test_for_loop_items():
    stateflow.core.clear()

    class ForOtherClass(object):
        def __init__(self):
            self.x = 0

        def set(self, x: int):
            self.x = x
            return self.a

        def bigger_than(self, x: int) -> bool:
            return x > self.x

    class ForClass(object):
        def __init__(self):
            self.a = 0
            self.b = 0

        def cool_method(self, others: List[ForOtherClass]):
            for x in range(0, 10):
                self.a = 0

                if self.a > 0:
                    continue

                self.a = 10

            self.a = 0

            for x in others:
                x.set(self.a * 3)
                self.a = 0

    stateflow.stateflow(ForClass, parse_file=False)
    stateflow.stateflow(ForOtherClass, parse_file=False)

    wrapper = stateflow.core.registered_classes[0]
    method_desc = stateflow.core.registered_classes[0].class_desc.get_method_by_name(
        "cool_method"
    )

    split = Split(
        [cls.class_desc for cls in stateflow.core.registered_classes],
        stateflow.core.registered_classes,
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.core.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )

    blocks: List[Block] = analyzer.blocks

    from stateflow.util import dataflow_visualizer

    print(dataflow_visualizer.visualize(blocks, True))
    method_desc.split_function(
        blocks, wrapper.class_desc.to_function_type().to_address()
    )
    print(dataflow_visualizer.visualize_flow(method_desc.flow_list))

    invoke_for: InvokeFor = [
        f for f in method_desc.flow_list if isinstance(f, InvokeFor)
    ][0]

    print(invoke_for.for_body_node)
    assert invoke_for.for_body_node != -1
    assert invoke_for.else_node == -1


def do_split(split, class_desc, method_name: str):
    method_desc = class_desc.get_method_by_name(method_name)

    analyzer = SplitAnalyzer(
        class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            class_desc,
        ),
        method_desc.method_node.body.children,
    )

    method_desc.split_function(
        analyzer.blocks, class_desc.to_function_type().to_address()
    )

    return analyzer, method_desc


def test_nested_execution():
    stateflow.core.clear()

    class OtherNestClass:
        def __init__(self, x: int):
            self.x = x

        def is_really_true(self):
            return True

        def is_true(self, other: "OtherNestClass"):
            is_really_true: bool = other.is_really_true()
            return is_really_true

        def nest_call(self, other: "OtherNestClass") -> bool:
            z = 0
            is_true = other.is_true()
            return is_true

    class NestClass:
        def __init__(self, x: int):
            self.x = x

        def nest_call(self, other: OtherNestClass):
            y = other.x
            z = 3

            if other.nest_call():
                p = 3

            other.nest_call()

            return y, z, p

    stateflow.stateflow(NestClass, parse_file=False)
    stateflow.stateflow(OtherNestClass, parse_file=False)

    split = Split(
        [cls.class_desc for cls in stateflow.core.registered_classes],
        stateflow.core.registered_classes,
    )

    nest_analyzer, nest_method = do_split(
        split, stateflow.core.registered_classes[0].class_desc, "nest_call"
    )
    nest_other, nest_other_method = do_split(
        split, stateflow.core.registered_classes[1].class_desc, "nest_call"
    )

    is_true, is_true_method = do_split(
        split, stateflow.core.registered_classes[1].class_desc, "is_true"
    )

    is_really_true, is_really_true_method = do_split(
        split, stateflow.core.registered_classes[1].class_desc, "is_really_true"
    )

    # We don't need to split it!
    is_really_true_method.flow_list = []

    from stateflow.split.execution_plan_merging import ExecutionPlanMerger

    merger = ExecutionPlanMerger(
        [cls.class_desc for cls in stateflow.core.registered_classes]
    )

    replace = merger.mark_replacement_nodes(is_really_true_method.flow_list)
    assert len(replace) == 0

    replace = merger.mark_replacement_nodes(is_true_method.flow_list)
    assert len(replace) == 0

    replace = merger.mark_replacement_nodes(nest_other_method.flow_list)
    assert len(replace) == 1

    replace = merger.mark_replacement_nodes(nest_method.flow_list)
    assert len(replace) == 4

    assert [x.id for x in is_true_method.flow_list] == [
        x.id for x in merger.replace_and_merge(is_true_method.flow_list)
    ]

    # Very shallow tests
    from stateflow.util.dataflow_visualizer import visualize_flow

    visualize_flow(merger.replace_and_merge(nest_other_method.flow_list))

    merged = merger.replace_and_merge(nest_method.flow_list)
    assert len(merged) == 27
