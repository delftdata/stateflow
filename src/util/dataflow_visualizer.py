from src.split.split_block import Block
from src.split.conditional_block import ConditionalBlock
from src.dataflow.event_flow import EventFlowNode, InvokeConditional
from typing import List
from graphviz import Digraph


def visualize(blocks: List[Block], code=False):
    dot = Digraph(comment="Visualized dataflow")

    nodes = []

    for b in blocks:
        if isinstance(b, ConditionalBlock):
            dot_node = dot.node(
                str(b.block_id),
                label=f"{b.block_id} - {b.label}" if not code else b.code(),
                _attributes={
                    "shape": "rectangle",
                    "fillcolor": "lightskyblue",
                    "style": "filled",
                },
            )
        else:
            dot_node = dot.node(
                str(b.block_id),
                label=f"{b.block_id} - {b.label}" if not code else b.code(),
                shape="rectangle",
            )
        nodes.append(dot_node)

    for b in blocks:
        if isinstance(b, ConditionalBlock):
            dot.edge(
                str(b.block_id),
                str(b.true_block.block_id),
                label="T",
                color="darkgreen",
                style="dotted",
            )
            dot.edge(
                str(b.block_id),
                str(b.false_block.block_id),
                label="F",
                color="crimson",
                style="dotted",
            )
        else:
            for next in b.next_block:
                dot.edge(str(b.block_id), str(next.block_id))

    print(dot.source)


def visualize_flow(flow: List[EventFlowNode]):
    dot = Digraph(comment="Visualized dataflow")

    nodes = []

    for n in flow:
        if isinstance(n, InvokeConditional):
            nodes.append(
                dot.node(
                    str(n.id),
                    label=str(n.typ),
                    _attributes={
                        "shape": "rectangle",
                        "fillcolor": "lightskyblue",
                        "style": "filled",
                    },
                )
            )
        else:
            nodes.append(
                dot.node(
                    str(n.id),
                    label=str(n.typ),
                )
            )

    for n in flow:
        if isinstance(n, InvokeConditional):
            conditional: InvokeConditional = n

            dot.edge(
                str(conditional.id),
                str(conditional.if_true_node),
                label="T",
                color="darkgreen",
                style="dotted",
            )
            dot.edge(
                str(conditional.id),
                str(conditional.if_false_node),
                label="F",
                color="crimson",
                style="dotted",
            )
        else:
            for next in n.next:
                dot.edge(str(n.id), str(next))

    print(dot.source)
