import libcst as cst
import libcst.matchers as m
from typing import Any


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


def extract_types(module_node: cst.CSTNode, node: cst.Annotation) -> Any:
    """
    Extracts the (evaluated) type of an Annotation object.

    :param module_node: the 'context' of this annotation: i.e. the module in which it was declared.
    :param node: the actual annotation object.
    :return: the evaluated type annotation.
    """
    return module_node.code_for_node(node.annotation)
