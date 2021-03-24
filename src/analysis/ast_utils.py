import libcst as cst
import libcst.matchers as m
from typing import Any, List


def is_self(node: cst.CSTNode) -> bool:
    """
    Verifies if an Attribute node, attributes to 'self'.
    This is used to find the self attributes of a class.

    :param node: the Attribute node to verify.
    :return: True if nod is an Attribute and the value is 'self'.
    """
    if m.matches(node, m.Attribute(value=m.Name(value="self"))):
        return True

    return False


def extract_types(
    module_node: cst.CSTNode, node: cst.Annotation, unpack: bool = False
) -> Any:
    """
    Extracts the (evaluated) type of an Annotation object.

    :param module_node: the 'context' of this annotation: i.e. the module in which it was declared.
    :param node: the actual annotation object.
    :param unpack: if the annotation holds a tuple, its unpacked and each element is individually evaluated.
    :return: the evaluated type annotation.
    """
    if unpack and m.matches(node.annotation, m.Subscript(value=m.Name(value="Tuple"))):
        types: List[Any] = []

        # Unpacks the Tuple as:
        # Subscript(value=Name(value="Tuple"), slice=[SubscriptElement(slice=Index(value=Name)),..])
        for tuple_element in node.annotation.slice:
            if m.matches(
                tuple_element, m.SubscriptElement(slice=m.Index(value=m.Name()))
            ):
                types.append(tuple_element.slice.value.value)
            elif m.matches(tuple_element, m.SubscriptElement(slice=m.Index())):
                types.append(module_node.code_for_node(tuple_element.slice.value))

        return types

    return module_node.code_for_node(node.annotation)
