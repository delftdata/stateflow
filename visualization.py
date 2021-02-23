from extraction import PyClass
from typing import List
from graphviz import Graph, Digraph
from pytypes import *


class Visualizer:
    def __init__(self, classes: List[PyClass] = []):
        self.classes = classes

    def visualize(self) -> Digraph:
        graph: Digraph = Digraph(f"Dataflow visualizer")
        graph.attr(compound="true", rankdir="LR")

        for clasz in self.classes:
            graph.node(
                f"{clasz.identifier}Request",
                shape="record",
                style="filled",
                fillcolor="lightgrey",
                color="black",
                fontname="times-bold",
            )
            graph.node(
                f"{clasz.identifier}Reply",
                shape="record",
                style="filled",
                fillcolor="lightgrey",
                color="black",
                fontname="times-bold",
            )
            with graph.subgraph(name=f"cluster_{clasz.identifier}") as cluster:
                cluster.attr(
                    color="black",
                    label=f"{clasz.identifier} stateful function",
                    fillcolor="white",
                    fontname="times-bold",
                )
                cluster.attr("node", fillcolor="white")
                main_edge = False
                for fun in clasz.funs:
                    cluster.node(
                        f"{clasz.identifier}_{fun.identifier}",
                        label=fun.identifier,
                        width="1.5",
                        shape="circle",
                        fixedsize="shape",
                    )
                    if not main_edge:
                        graph.edge(
                            f"{clasz.identifier}Request",
                            f"{clasz.identifier}_{fun.identifier}",
                            lhead=f"cluster_{clasz.identifier}",
                            minlen="5.0",
                        )
                        graph.edge(
                            f"{clasz.identifier}_{fun.identifier}",
                            f"{clasz.identifier}Reply",
                            ltail=f"cluster_{clasz.identifier}",
                            minlen="5.0",
                        )
                        main_edge = True

                    input_args = "\\l".join(
                        [f"{param.name}: {param.type}" for param in fun.args]
                    )

                    if input_args == "":
                        input_args = "No input"

                    if len(fun.return_values) == 0:
                        output_args = "No output"
                    else:
                        output_args = "\\l".join(
                            [
                                f"return_arg {i}: {t[1]}"
                                for i, t in enumerate(fun.return_values[0].items())
                            ]
                        )

                    cluster.node(
                        f"{clasz.identifier}_{fun.identifier}_input",
                        label=input_args,
                        shape="rect",
                        style="filled",
                        fillcolor="lightgrey",
                    )
                    cluster.node(
                        f"{clasz.identifier}_{fun.identifier}_output",
                        label=output_args,
                        shape="rect",
                        style="filled",
                        fillcolor="lightgrey",
                    )
                    cluster.edge(
                        f"{clasz.identifier}_{fun.identifier}_input",
                        f"{clasz.identifier}_{fun.identifier}",
                    )
                    # Links to other nodes
                    write_color = "darkgreen"
                    for fun_ref in fun.fun_dependency:
                        if fun_ref.write_state:
                            write_color = "crimson"
                        else:
                            write_color = "darkgreen"

                        graph.edge(
                            f"{clasz.identifier}_{fun.identifier}",
                            f"{fun_ref}_input",
                            style="dashed",
                            color=write_color,
                        )
                        graph.edge(
                            f"{fun_ref}_output",
                            f"{clasz.identifier}_{fun.identifier}",
                            style="dashed",
                            color=write_color,
                        )

                    for param in fun.args:
                        if isinstance(param.type, PyClassRef):
                            graph.edge(
                                f"{clasz.identifier}_{fun.identifier}_input",
                                f"{param.type}_state",
                                style="dashed",
                                color=write_color,
                            )

                    cluster.edge(
                        f"{clasz.identifier}_{fun.identifier}",
                        f"{clasz.identifier}_{fun.identifier}_output",
                    )

                state_list = "\\l".join([f"{k}: {v}" for k, v in clasz.state.type_map])
                cluster.node(
                    name=f"{clasz.identifier}_state", label=state_list, shape="cylinder"
                )

        return graph
