from typing import List, Tuple, Any, Optional, Dict
import libcst as cst
from src.dataflow.stateful_fun import StatefulFun, NoType
from src.dataflow.state import StateDescription
from src.analysis.extract_stateful_method import ExtractStatefulMethod
from src.dataflow.method_descriptor import MethodDescriptor
import libcst.helpers as helpers
import libcst.matchers as m


class ExtractStatefulFun(cst.CSTVisitor):
    """Visits a ClassDefinition and extracts information to create a StatefulFunction."""

    def __init__(self, module_node: cst.CSTNode):
        self.module_node = module_node

        # Name of the class and if it is already defined.
        self.is_defined: bool = False
        self.class_name: str = None

        # Used to extract state.
        self.self_attributes: List[Tuple[str, Any]] = []

        # Keep track of all extracted methods.
        self.method_descriptor: List[MethodDescriptor] = []

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
        """Visits a function definition and analyze it.

        Extracts the following properties of a function:
        1. The declared self variables (i.e. state).
        2. The input variables of a function.
        3. The output variables of a function.
        4. If a function is read-only.

        :param node: the node to analyze.
        :return: always returns False.
        """
        if m.matches(node.asynchronous, cst.Asynchronous()):
            raise AttributeError(
                "Function within a stateful function cannot be defined asynchronous."
            )

        method_extractor: ExtractStatefulMethod = ExtractStatefulMethod(
            self.module_node, node
        )
        node.visit(method_extractor)

        # Get self attributes of the function and add to the attributes list of the class.
        self.self_attributes.extend(method_extractor.self_attributes)

        # Create a wrapper for this analyzed class method.
        self.method_descriptor.append(
            ExtractStatefulMethod.create_method_descriptor(method_extractor)
        )

        # We don't need to visit the FunctionDefs, we already analyze them in ExtractStatefulFun
        return False

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        """Visits a class and extracts useful information.

        This retrieves the name of the class and ensures that no nested classes are defined.

        :param node: the class definition to analyze.
        """

        if self.is_defined:  # We don't allow nested classes.
            raise AttributeError("Nested classes are not allowed.")

        self.is_defined = True
        self.class_name = helpers.get_full_name_for_node(node)

    def merge_self_attributes(self) -> Dict[str, any]:
        """Merges all self attributes.

        Merges all collected declarations attributing to 'self' into a dictionary. A key can only exist once.
        Type hints are stored as value for the key. Conflicting type hints for the same key will throw an error.
        Keys without type hints are valued as 'NoType'. Example:
        ```
        self.x : int = 3
        self.y, self.z = 4
        ```
        will be stored as: `{"x": "int", "y": "NoType", "z": "NoType"}`

        :return: the merged attributes.
        """
        attributes = {}

        for var_name, typ in self.self_attributes:
            if var_name in attributes:
                if typ == NoType:  # Skip NoTypes.
                    continue
                elif (
                    attributes[var_name] == "NoType"
                ):  # If current type is NoType, update to an actual type.
                    attributes[var_name] = typ
                elif (
                    typ != attributes[var_name]
                ):  # Throw error when type hints conflict.
                    raise AttributeError(
                        f"Stateful Function {self.class_name} has two declarations of {var_name} with different types {typ} != {attributes[var_name]}."
                    )

            else:
                if typ == NoType:
                    typ = "NoType"  # Rename NoType to a proper str.

                attributes[var_name] = typ

        return attributes

    @staticmethod
    def create_stateful_fun(analyzed_visitor: "ExtractStatefulFun") -> StatefulFun:
        """Creates a Stateful function.

        Leverages the analyzed visitor to create a Stateful Function.

        :param analyzed_visitor: the visitor that walked the ClassDef tree.
        :return: a Stateful Function object.
        """
        state_desc: StateDescription = StateDescription(
            analyzed_visitor.merge_self_attributes()
        )
        return StatefulFun(
            class_name=analyzed_visitor.class_name,
            state_desc=state_desc,
        )
