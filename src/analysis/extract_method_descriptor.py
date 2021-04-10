import libcst as cst
from typing import List, Tuple, Any, Optional, Set, Dict
from src.analysis import ast_utils
import libcst.matchers as m
from src.dataflow.stateful_operator import NoType
from src.descriptors import (
    MethodDescriptor,
    InputDescriptor,
    OutputDescriptor,
)


class ExtractMethodDescriptor(cst.CSTVisitor):
    """Visits a FunctionDef and extracts information to create a MethodWrapper.
    Assumes FunctionDef is part of ClassDef."""

    def __init__(self, class_node: cst.CSTNode, fun_node: cst.FunctionDef):
        self.class_node = class_node
        self.fun_node = fun_node

        self.method_name: str = fun_node.name.value

        # We build the return signature for this function based on the type hint.
        self.return_signature = self.extract_return_signature()

        # Keeps track of all self attributes in this function.
        # This is used to extract state of a complete class.
        self.self_attributes: List[Tuple[str, Any]] = []

        # Keep track of all parameters of this function.
        # We also use this to verify if a parameter call or attribute is properly typed.
        self.parameters: List[Tuple[str, Any]] = []

        # Keep track of all (potential) returns of this function.
        self.returns: List[List[Any]] = []

        # We assume a method is read-only until we find a 'self' assignment.
        self.read_only = True

        # We use this set to verify if a method has one or more external invocations.
        # The set stores names of all the attributes.
        self.external_attributes: Set[str] = {}

        # We also keep track of the typed declarations.
        # We need to match an attribute to the correct type.
        self.typed_declarations: Dict[str, str] = {}

    def extract_return_signature(self) -> Optional[List[Any]]:
        """Extracts a signature from the return annotation.

        Attempts to get the types as given in the return annotation of a function definition.
        If it is a tuple, each element is individually evaluated.

        :return: a list of types.
        """
        if self.fun_node.returns is None:
            return None

        annotation: cst.Annotation = self.fun_node.returns
        signature: Any = ast_utils.extract_types(
            self.class_node, annotation, unpack=True
        )

        # If it is not a list, we make it a list.
        if not isinstance(signature, list):
            signature = [signature]

        return signature

    def visit_Return(self, node: cst.Return):
        """A Return is visited to extract a method's OutputDescriptor.

        This method:
        1. Counts the amount of return variables.
        2. If a return signature exists, tries to match it.
        3. Verifies if a return contains call, which is not allowed.

        :param node: the return param.
        """
        if m.findall(node, m.Call()):  # We don't allow calls in a return node.
            raise AttributeError(
                f"Doing a function call in a return statement is not permitted."
            )

        amount_of_returns = 0

        # If we deal with a tuple, we consider multiple return variables.
        # E.g. return x, y, z will return a Tuple of x, y and z.
        if m.matches(node, m.Return(value=m.Tuple())):
            amount_of_returns = len(node.value.elements)
        elif node.value is not None:  # You can also call return without a value.
            amount_of_returns = 1

        # If we don't have a return signature, we consider all return values to be "NoType".
        if not self.return_signature:
            self.returns.append(list(["NoType" for _ in range(0, amount_of_returns)]))
            return

        # We don't want a mismatch between the length of the signature and the actual amount.
        if len(self.return_signature) != amount_of_returns:
            raise AttributeError(
                f"The return annotation defines {len(self.return_signature)} variables, "
                f"whereas a return statement only returns {amount_of_returns} variables."
            )

        self.returns.append(
            list([self.return_signature[i] for i in range(0, amount_of_returns)])
        )

    def visit_Param(self, node: cst.Param) -> Optional[bool]:
        """A Param is visited to extract a method's InputDescriptor.

        :param node: the node param.
        """
        # We don't allow default values.
        if m.matches(node.equal, m.AssignEqual()):
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

    def visit_Attribute(self, node: cst.Attribute) -> Optional[bool]:
        """Verifies that attributes on parameters are always typed.

        When a parameter is used for attribution (i.e. function call or state update),
        we need to know it's type. Especially if another stateful function is called,
        we need to know which function. An error is thrown when these parameters are not typed.

        If a parameter get's overriden, we still throw the error. For now, we consider this an edge case.
        For example:

        def fun(self, x):
            self.x -= x
            x: Item = Item()
            x.call()

        This will throw an error because x is untyped in the parameters, but it's overriden in the function.

        :param node: an attribute node which is checked to use a parameter.
        """
        if isinstance(node.value, cst.Name) and node.value.value != "self":
            for k, v in self.parameters:
                if k == node.value.value and v == "NoType":
                    raise AttributeError(
                        f"This method attributes the parameter {k} (i.e. function call or state access). "
                        f"However, no type hint is given."
                    )


            # We are now having an attribute access of 'another' instance.
            self.external_invocation.add(node.value.value)



    def visit_AnnAssign(self, node: cst.AnnAssign) -> Optional[bool]:
        """Visit an AnnAssign to extract a StateDescriptor.

        This function verifies if an AnnAssign updates state. This way, we can extract
        all internal state of a class.

        :param node: the AnnAssign to check.
        """
        if ast_utils.is_self(node.target) and m.matches(node.target.attr, m.Name()):
            annotation = ast_utils.extract_types(self.class_node, node.annotation)
            self.self_attributes.append((node.target.attr.value, annotation))

            self.read_only = False

    def visit_AugAssign(self, node: cst.AugAssign) -> Optional[bool]:
        """Visit an AugAssign to extract a StateDescriptor.

        This function verifies if an AugAssign updates state. This way, we can extract
        all internal state of a class.

        :param node: the AugAssign to check.
        """
        if ast_utils.is_self(node.target) and m.matches(node.target.attr, m.Name()):
            self.self_attributes.append((node.target.attr.value, NoType))

            self.read_only = False

    def visit_AssignTarget(self, node: cst.AssignTarget) -> None:
        """Visit an AssignTarget to extract a StateDescriptor.

        This function verifies if an AssignTarget updates state. This way, we can extract
        all internal state of a class. If we deal with a tuple, we iterate over each element separately.

        :param node: the AssignTarget to check.
        """
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
        analyzed_method: "ExtractMethodDescriptor",
    ) -> MethodDescriptor:
        """Creates a descriptor of this method.

        A descriptor involves:
        1. The parameters of this method.
        2. The return paths of this method.
        3. Whether the function is read-only.

        :param analyzed_method: the ExtractStatefulMethod instance that analyzed the method.
        :return: a MethodDescriptor of the analyzed method.
        """
        parameter_dict = {k: v for k, v in analyzed_method.parameters}
        input_desc: InputDescriptor = InputDescriptor(parameter_dict)

        # We verify if 'self' is part of the input. This is necessity.
        if "self" not in input_desc:
            raise AttributeError(
                "We expect all functions in a class to be method, which requires the first attribute to be 'self'."
            )
        # Afterwards we delete it.
        del input_desc["self"]

        # Create an OutputDescriptor.
        output_desc: OutputDescriptor = OutputDescriptor(analyzed_method.returns)

        return MethodDescriptor(
            analyzed_method.method_name,
            analyzed_method.read_only,
            input_desc,
            output_desc,
        )
