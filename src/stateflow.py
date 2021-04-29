from inspect import isclass, getsource, getfile
import libcst as cst
from typing import List, Dict
from src.wrappers.class_wrapper import ClassWrapper
from src.wrappers.meta_wrapper import MetaWrapper
from src.dataflow.dataflow import Dataflow, Ingress, Egress
from src.dataflow.stateful_operator import StatefulOperator, Edge, Operator
from src.dataflow.event import FunctionType, EventType
from src.descriptors import *
from src.analysis.extract_class_descriptor import ExtractClassDescriptor
from src.split.split import Split

parse_cache: Dict[str, cst.Module] = {}

registered_classes: List[ClassWrapper] = []
meta_classes: List = []


def stateflow(cls):
    if not isclass(cls):
        raise AttributeError(f"Expected a class but got an {cls}.")

    # Parse source.
    class_file_name = getfile(cls)
    if class_file_name not in parse_cache:
        with open(getfile(cls), "r") as file:
            to_parse_file = file.read()

        parsed_file = cst.parse_module(to_parse_file)
        parse_cache[class_file_name] = parsed_file
    else:
        parsed_file = parse_cache[class_file_name]

    wrapper = cst.metadata.MetadataWrapper(parsed_file)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    # Extract class description.
    extraction: ExtractClassDescriptor = ExtractClassDescriptor(
        parsed_file, cls.__name__, expression_provider
    )
    wrapper.visit(extraction)

    # Create ClassDescriptor
    class_desc: ClassDescriptor = ExtractClassDescriptor.create_class_descriptor(
        extraction
    )

    # Register the class.
    registered_classes.append(ClassWrapper(cls, class_desc))

    # Create a meta class..
    meta_class = MetaWrapper(
        str(cls.__name__),
        tuple(cls.__bases__),
        dict(cls.__dict__),
        descriptor=class_desc,
    )
    meta_classes.append(meta_class)

    return meta_class


def _build_dataflow(
    registered_classes: List[ClassWrapper], meta_classes: List[MetaWrapper]
) -> Dataflow:
    operators: List[Operator] = []
    edges: List[Edge] = []

    for wrapper, meta_class in zip(registered_classes, meta_classes):
        name: str = wrapper.class_desc.class_name
        fun_type: FunctionType = FunctionType.create(wrapper.class_desc)

        # Create operator, we will add the edges later.
        operator: StatefulOperator = StatefulOperator(
            [], [], fun_type, wrapper, meta_class
        )

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
    if len(registered_classes) == 0 or len(meta_classes) == 0:
        raise AttributeError(
            "Trying to initialize stateflow without any registered classes. "
            "Please register one using the @stateflow decorator."
        )

    # We now link classes to each other.
    class_descs: List[ClassDescriptor] = [
        wrapper.class_desc for wrapper in registered_classes
    ]

    for desc in class_descs:
        desc.link_to_other_classes(class_descs)

    # We execute the split phase
    split: Split = Split(class_descs, registered_classes)
    split.split_methods()

    flow: Dataflow = _build_dataflow(registered_classes, meta_classes)

    ### DEBUG
    operator_names: List[str] = [
        op.class_wrapper.class_desc.class_name for op in flow.operators
    ]
    print(
        f"Registered {len(flow.operators)} operators with the names: {operator_names}."
    )
    ###
    return flow
