from runtime.runtime import Runtime
from inspect import isclass, getsource
import libcst as cst
from typing import List
from src.descriptors import ClassDescriptor
from src.wrappers import ClassWrapper
from src.analysis.extract_class_descriptor import ExtractClassDescriptor
from src.dataflow import (
    Dataflow,
    FunctionType,
    StatefulOperator,
    Ingress,
    Egress,
    EventType,
    Edge,
    Operator,
)

registered_classes: List[ClassWrapper] = []


def stateflow(cls):
    if not isclass(cls):
        raise AttributeError(f"Expected a class but got an {cls}.")

    # Parse
    class_source = getsource(cls)
    parsed_class = cst.parse_module(class_source)

    # Extract
    extraction: ExtractClassDescriptor = ExtractClassDescriptor(parsed_class)
    parsed_class.visit(extraction)

    # Create ClassDescriptor
    class_desc: ClassDescriptor = ExtractClassDescriptor.create_class_descriptor(
        extraction
    )

    # Register the class.
    registered_classes.append(ClassWrapper(cls, class_desc))


def build_dataflow(registered_classes: List[ClassWrapper]) -> Dataflow:
    operators: List[Operator] = []
    edges: List[Edge] = []

    for wrapper in registered_classes:
        name: str = wrapper.class_desc.class_name
        fun_type: FunctionType = FunctionType.create(wrapper)

        # Create operator, we will add the edges later.
        operator: StatefulOperator = StatefulOperator([], [], fun_type, wrapper)

        incoming_edges: List[Edge] = []
        outgoing_edges: List[Edge] = []

        # For all functions we have an incoming ingress and outgoing egress
        ingress: Ingress = Ingress(f"{name}-input", operator, EventType.Request)
        egress: Egress = Ingress(f"{name}-input", operator, EventType.Request)

        incoming_edges.append(ingress)
        outgoing_edges.append(egress)

        operator.incoming_edges = incoming_edges
        operator.outgoing_edges = outgoing_edges

        operators.append(operator)
        edges.extend(incoming_edges + outgoing_edges)

    return Dataflow(operators, edges)


def init():
    if len(registered_classes) == 0:
        raise AttributeError(
            "Trying to initialize stateflow without any registered classes. "
            "Please register one using the @stateflow decorator."
        )

    flow: Dataflow = build_dataflow(registered_classes)

    ### DEBUG
    operator_names: List[str] = [
        op.class_wrapper.class_desc.class_name for op in flow.operators
    ]
    print(
        f"Registered {len(flow.operators)} operators with the names: {operator_names}."
    )
    ###


class StateFlow:
    def __init__(self, runtime: Runtime):
        self.runtime = runtime

    def run(self):
        self.runtime.run()
