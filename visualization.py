from extraction import PyClass
from typing import List
from graphviz import Graph, Digraph


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
                        [f"{fun_arg[0]}: {fun_arg[1]}" for fun_arg in fun.args.items()]
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
                        shape="record",
                        style="filled",
                        fillcolor="lightgrey",
                    )
                    cluster.node(
                        f"{clasz.identifier}_{fun.identifier}_output",
                        label=output_args,
                        shape="record",
                        style="filled",
                        fillcolor="lightgrey",
                    )
                    cluster.edge(
                        f"{clasz.identifier}_{fun.identifier}_input",
                        f"{clasz.identifier}_{fun.identifier}",
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