from src.split.split_block import Block
from typing import List
from graphviz import Digraph


def visualize(blocks: List[Block]):
    dot = Digraph(comment="Visualized dataflow")

    nodes = []

    for b in blocks:
        nodes.append(
            dot.node(
                str(b.block_id),
                label=f"{str(b.block_id)} - {b.get_label()}",
            )
        )

    for b in blocks:
        for next in b.next_block:
            dot.edge(str(b.block_id), str(next.block_id))

    print(dot.source)
