import libcst as cst
from typing import List, Tuple, Any, Optional
from src.analysis import ast_utils
import libcst.matchers as m
from src.dataflow.stateful_fun import NoType
from src.dataflow.method_descriptor import MethodDescriptor, InputDescriptor


class ExtractStatefulMethod(cst.CSTVisitor):
    """Visits a FunctionDef and extracts information to create a MethodWrapper.
    Assumes FunctionDef is part of ClassDef."""

    def __init__(self, class_node: cst.CSTNode, fun_node: cst.CSTNode):
        self.class_node = class_node
        self.fun_node = fun_node

        # Keeps track of all self attributes in this function.
        # This is used to extract state of a complete class.
        self.self_attributes: List[Tuple[str, Any]] = []

        # Keep track of all parameters of this function.
        # We also use this to verify if a parameter call or attribute is properly typed.
        self.parameters: List[Tuple[str, Any]] = []

        # We assume a method is read-only until we find a self assignment.
        self.read_only = True

    def visit_Param(self, node: cst.Param) -> Optional[bool]:
        """A Param is visited to extract a method's InputDescriptor.

        :param node: the node param.
        """
        # We don't allow default values.
        if m.matches(node.equal, cst.AssignEqual()):
            raise AttributeError(
                "Default values are currently not supported for class methods."
            )

        # We don't allow non-positional parameters.
        if node.star == "*" or node.star == "**":
            raise AttributeError(
                "*args and **kwargs are currently not supported for class methods."
            )

        param_name = node.name.value

        # If we have an annotation, we extract its type.
        if node.annotation:
            param_type = ast_utils.extract_types(self.class_node, node.annotation)
        else:
            param_type = "NoType"

        self.parameters.append((param_name, param_type))

    def visit_AnnAssign(self, node: cst.AnnAssign) -> Optional[bool]:
        if ast_utils.is_self(node.target) and m.matches(node.target.attr, m.Name()):
            annotation = ast_utils.extract_types(self.class_node, node.annotation)
            self.self_attributes.append((node.target.attr.value, annotation))

            self.read_only = False

    def visit_AugAssign(self, node: cst.AugAssign) -> Optional[bool]:
        if ast_utils.is_self(node) and m.matches(node.target.attr, m.Name()):
            self.self_attributes.append((node.target.attr.value, NoType))

            self.read_only = False

    def visit_AssignTarget(self, node: cst.AssignTarget) -> None:
        if not m.matches(node, m.AssignTarget(target=m.Tuple())):
            if ast_utils.is_self(node.target) and m.matches(node.target.attr, m.Name()):
                self.self_attributes.append((node.target.attr.value, NoType))

                self.read_only = False

        # We assume it is a Tuple now.
        if m.matches(node, m.AssignTarget(target=m.Tuple())):
            for element in node.target.elements:
                if (
                    m.matches(element, m.Element())
                    and ast_utils.is_self(element.value)
                    and m.matches(element.value.attr, m.Name())
                ):
                    self.self_attributes.append((element.value.attr.value, NoType))

                    self.read_only = False

    @staticmethod
    def create_method_descriptor(
        analyzed_tree: "ExtractStatefulMethod",
    ) -> MethodDescriptor:
        parameter_dict = {k: v for k, v in analyzed_tree.parameters}
        input_desc = InputDescriptor(parameter_dict)

        # We verify if 'self' is part of the input. This is necessity.
        if "self" not in input_desc:
            raise AttributeError(
                "We expect all functions in a class to be method, which requires the first attribute to be 'self'."
            )
        # Afterwards we delete it.
        del input_desc["self"]

        return MethodDescriptor(analyzed_tree.read_only, input_desc)
