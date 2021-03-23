import libcst as cst
import libcst.matchers as m


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
