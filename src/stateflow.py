from inspect import isclass, getsource
import libcst as cst
from typing import List
from src.dataflow import *
from src.wrappers import *
from src.descriptors import *
from src.analysis.extract_class_descriptor import ExtractClassDescriptor
from src.split.split import Split

registered_classes: List[ClassWrapper] = []
meta_classes: List["GenericMeta"] = []


def stateflow(cls):
    if not isclass(cls):
        raise AttributeError(f"Expected a class but got an {cls}.")

    # Parse source.
    class_source = getsource(cls)
    parsed_class = cst.parse_module(class_source)

    wrapper = cst.metadata.MetadataWrapper(parsed_class)
    expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

    # Extract class description.
    extraction: ExtractClassDescriptor = ExtractClassDescriptor(
        parsed_class, expression_provider
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
    split: Split = Split(class_descs)
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
