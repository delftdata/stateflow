import pytest
from src.split.split_analyze import (
    SplitAnalyzer,
    Split,
    RemoveAfterClassDefinition,
    SplitTransformer,
    SplitContext,
    Block,
    StatementBlock,
    ConditionalBlock,
)
from src.dataflow.event_flow import (
    StartNode,
    InvokeExternal,
    InvokeSplitFun,
    ReturnNode,
    RequestState,
    InvokeConditional,
)
from typing import List
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
        a_wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            a_wrapper.class_desc.expression_provider,
            a_method_desc.method_node,
            a_method_desc,
            stateflow.registered_classes[0].class_desc,
        ),
        a_method_desc.method_node.body.children,
    )
    stmts = analyzer.blocks

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
        a_wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            a_wrapper.class_desc.expression_provider,
            a_method_desc.method_node,
            a_method_desc,
            stateflow.registered_classes[0].class_desc,
        ),
        a_method_desc.method_node.body.children,
    )
    stmts = analyzer.blocks

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
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.registered_classes[0].class_desc,
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
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )
    stmts = analyzer.blocks

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
    assert stmts[1].dependencies == ["a", "c", "get_return"]
    assert stmts[1].definitions == ["b_result", "new_a"]

    assert stmts[2].dependencies == ["b_result", "a", "set_return"]
    assert stmts[2].definitions == ["c_result"]

    # GET STATE -> GET STATE -> INVOKE SPLIT FUN -> INVOKE EXTERNAL
    node_one = stmts[0].build_event_flow_nodes(0)

    assert len(node_one) == 4

    assert node_one[0].id == 1 and isinstance(node_one[0], RequestState)
    assert node_one[0].next == [node_one[1].id]
    assert node_one[0].var_name == "b"
    assert node_one[0].fun_type.name == "BB"

    assert node_one[1].id == 2 and isinstance(node_one[1], RequestState)
    assert node_one[1].previous == node_one[0].id
    assert node_one[1].next == [node_one[2].id]
    assert node_one[1].var_name == "c"
    assert node_one[1].fun_type.name == "CC"

    assert node_one[2].id == 3 and isinstance(node_one[2], InvokeSplitFun)
    assert node_one[2].previous == node_one[1].id
    assert node_one[2].next == [node_one[3].id]
    assert node_one[2].fun_type.name == "AA"

    assert node_one[3].id == 4 and isinstance(node_one[3], InvokeExternal)
    assert node_one[3].previous == node_one[2].id
    assert node_one[3].next == []
    assert node_one[3].fun_type.name == "BB"

    node_last = stmts[-1].build_event_flow_nodes(0)
    assert len(node_last) == 2
    assert node_last[0].id == 1 and isinstance(node_last[0], InvokeSplitFun)
    assert node_last[0].fun_type.name == "AA"

    assert node_last[1].id == 2 and isinstance(node_last[1], ReturnNode)
    assert node_last[1].previous == node_last[0].id

    node_inter = stmts[1].build_event_flow_nodes(0)
    assert len(node_inter) == 2
    assert node_inter[0].id == 1 and isinstance(node_inter[0], InvokeSplitFun)
    assert node_inter[0].fun_type.name == "AA"
    assert node_inter[1].id == 2 and isinstance(node_inter[1], InvokeExternal)
    assert node_inter[1].fun_type.name == "CC"


def test_multiple_splits_with_returns():
    stateflow.clear()

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
            a = self.a + self.b

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
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )
    stmts = analyzer.blocks

    # GET STATE -> GET STATE -> INVOKE SPLIT FUN -> INVOKE EXTERNAL
    node_one = stmts[0].build_event_flow_nodes(0)

    from src.util import dataflow_visualizer

    dataflow_visualizer.visualize_flow(node_one)
    dataflow_visualizer.visualize(stmts, code=True)
    print(stmts[0].code())
    print(stmts[1].code())

    assert len(node_one) == 3

    assert node_one[0].id == 1 and isinstance(node_one[0], RequestState)
    assert node_one[0].var_name == "b"
    assert node_one[0].fun_type.name == "BBB"

    assert node_one[1].id == 2 and isinstance(node_one[1], RequestState)
    assert node_one[1].var_name == "c"
    assert node_one[1].fun_type.name == "CCC"

    assert node_one[2].id == 3 and isinstance(node_one[2], InvokeSplitFun)
    assert node_one[2].fun_type.name == "AAA"

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
        and node_four[1].fun_type.name == "BBB"
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
    stateflow.clear()

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

    wrapper = stateflow.registered_classes[0]
    method_desc = stateflow.registered_classes[0].class_desc.get_method_by_name(
        "cool_method"
    )

    split = Split(
        [cls.class_desc for cls in stateflow.registered_classes],
        stateflow.registered_classes,
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )

    blocks: List[Block] = analyzer.blocks

    from src.util import dataflow_visualizer

    dataflow_visualizer.visualize(blocks)

    # Check unique id's
    assert len([b.block_id for b in blocks]) == len(set([b.block_id for b in blocks]))

    """ block 0
    a = self.a + self.b
    """
    assert isinstance(blocks[0], StatementBlock)
    assert (
        blocks[0].dependencies == []
    )  # Actually it has dependencies, but those are in the parameters we assume.
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

    method_desc.split_function(blocks)
    dataflow_visualizer.visualize(blocks, True)
    dataflow_visualizer.visualize_flow(method_desc.flow_list)


def test_if_non_split():
    stateflow.clear()

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

    wrapper = stateflow.registered_classes[0]
    method_desc = stateflow.registered_classes[0].class_desc.get_method_by_name(
        "invoke"
    )
    split = Split(
        [cls.class_desc for cls in stateflow.registered_classes],
        stateflow.registered_classes,
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )

    blocks: List[Block] = analyzer.blocks

    from src.util import dataflow_visualizer

    dataflow_visualizer.visualize(blocks, True)

    method_desc.split_function(blocks)

    dataflow_visualizer.visualize_flow(method_desc.flow_list)


def test_if_statements_complex():
    stateflow.clear()

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

    wrapper = stateflow.registered_classes[0]
    method_desc = stateflow.registered_classes[0].class_desc.get_method_by_name(
        "cool_method"
    )

    split = Split(
        [cls.class_desc for cls in stateflow.registered_classes],
        stateflow.registered_classes,
    )

    analyzer = SplitAnalyzer(
        wrapper.class_desc.class_node,
        SplitContext(
            split.name_to_descriptor,
            wrapper.class_desc.expression_provider,
            method_desc.method_node,
            method_desc,
            stateflow.registered_classes[0].class_desc,
        ),
        method_desc.method_node.body.children,
    )

    blocks: List[Block] = analyzer.blocks

    from src.util import dataflow_visualizer

    dataflow_visualizer.visualize(blocks, True)

    method_desc.split_function(blocks)

    dataflow_visualizer.visualize_flow(method_desc.flow_list)
