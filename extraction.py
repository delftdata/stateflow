import inspect
import ast
from collections import OrderedDict
from typing import *
from pytypes import *
import logging


class ClassExtraction:
    def __init__(self, cls):
        if not inspect.isclass(cls):
            raise AttributeError(f"Expected a class but got an {cls}.")
        self.identifier = cls.__name__
        self.ast = ast.parse(inspect.getsource(cls))

    def get(self) -> PyClass:
        funs: List[PyFunc] = self.get_functions()
        state: PyState = self.get_state()

        return PyClass(self.identifier, funs, state, self.ast)

    def get_state(self) -> PyState:
        state: Dict = {}

        for body_node in ast.walk(self.ast):
            if isinstance(body_node, ast.Assign) or isinstance(
                body_node, ast.AnnAssign
            ):
                partial_state = self.__parse_assign_node(body_node)
                for k, v in partial_state.items():
                    if (
                        k in state and state[k] is None
                    ):  # If state already exists, but without type annotation. Set the type.
                        state[k] = v
                    elif k in state and state[k] is not None:
                        continue
                    else:
                        state[k] = v
        return PyState(
            f"{self.identifier}_state",
            keys=list(state.keys()),
            type_map=list(state.items()),
        )

    def get_functions(self) -> List[PyFunc]:
        ids: List[str] = []
        funs: List[PyFunc] = []

        for node in ast.walk(self.ast):
            if isinstance(node, ast.FunctionDef):
                if node.name == "__hash__":  # We ignore hash functions for now.
                    continue
                parsed_fun: PyFunc = self.__parse_function(node)
                fun_id: str = parsed_fun.identifier

                # If the same function already exists, override it.
                if fun_id in ids:
                    logging.info(
                        f"{fun_id} is already extracted, overriding with the latest function definition."
                    )
                    idx = ids.index(fun_id)
                    del funs[idx]
                    del ids[idx]

                ids.append(fun_id)
                funs.append(parsed_fun)

        return funs

    def __parse_function(self, fun_node: ast.FunctionDef) -> PyFunc:
        # Extract arguments.
        fun_args: list[ast.arguments] = fun_node.args
        parsed_fun_args: List[PyParam] = []
        for i, arg in enumerate(fun_args.args):
            if i == 0 and arg.arg == "self":  # Self arguments are skipped.
                continue

            # Check if there is a type annotation.
            annotation = None
            if arg.annotation is not None:
                annotation = arg.annotation.id

            parsed_fun_args.append(PyParam(arg.arg, annotation))

        # Extract return values.
        parsed_return_vals: List[OrderedDict] = []
        return_annotations: List[str] = []
        if fun_node.returns is not None:  # Extract return type annotation.
            if isinstance(
                fun_node.returns, ast.Name
            ):  # Consider a simple type annotation like; str, int, list, etc.
                return_annotations.append(fun_node.returns.id)
            elif (
                isinstance(fun_node.returns, ast.Subscript)
                and isinstance(fun_node.returns.value, ast.Name)
                and fun_node.returns.value.id == "Tuple"
            ):  # Consider a typ like Tuple[int, str]
                if isinstance(
                    fun_node.returns.slice.value, ast.Name
                ):  # Tuple with only 1 type.
                    return_annotations.append(fun_node.returns.slice.value.id)
                elif isinstance(
                    fun_node.returns.slice.value, ast.Tuple
                ):  # Tuple with multiple types.
                    [
                        return_annotations.append(ann.id)
                        for ann in fun_node.returns.slice.value.elts
                    ]
        write_state = False
        for body_node in ast.walk(fun_node):
            if isinstance(body_node, ast.Return):
                return_value: OrderedDict = self.__parse_return_node(
                    body_node, return_annotations
                )
                if return_value is not None:
                    parsed_return_vals.insert(0, return_value)
            # find if read or write
            if (
                isinstance(body_node, ast.Assign)
                or isinstance(body_node, ast.AnnAssign)
                or isinstance(body_node, ast.AugAssign)
            ):
                target_node = (
                    body_node.targets[0]
                    if isinstance(body_node, ast.Assign)
                    else body_node.target
                )

                for assign_node in ast.walk(target_node):
                    if (
                        isinstance(assign_node, ast.Name) and assign_node.id == "self"
                    ):  # Now we're updating self
                        write_state = True

        return PyFunc(
            identifier=fun_node.name,
            args=parsed_fun_args,
            return_values=parsed_return_vals,
            ast=fun_node,
            write_state=write_state,
        )

    def __parse_return_node(
        self, return_node: ast.Return, annotation: List[str]
    ) -> OrderedDict:
        return_dict: OrderedDict = OrderedDict()

        value = return_node.value
        if value is None:
            return None
        elif isinstance(value, ast.Tuple):
            if len(annotation) == len(value.elts):
                for i, _ in enumerate(value.elts):
                    return_dict[f"return_value_{i}"] = annotation[i]
            else:
                logging.warning(
                    f"Expected {len(annotation)} return arguments, but got {value}. Annotated all types with None."
                )
                for i, _ in enumerate(value.elts):
                    return_dict[f"return_value_{i}"] = None
        else:

            if len(annotation) > 0:
                return_dict["return_value_0"] = annotation[0]
            else:
                return_dict["return_value_0"] = None
        return return_dict

    def __parse_assign_node(self, assign_node) -> Dict:
        state = {}
        if isinstance(assign_node, ast.Assign):
            for target in assign_node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    if target.attr not in state:
                        state[target.attr] = None
        if isinstance(assign_node, ast.AnnAssign):
            target = assign_node.target
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                state[target.attr] = assign_node.annotation.id
        return state


class ClassDependencyResolver:
    def __init__(self, classes: List[PyClass]):
        self.classes = classes
        self.class_keys = [c.identifier for c in self.classes]

    def resolve(self):
        # Since Python interprets code, we need to do a pass again over the AST's to find it's dependency
        for clasz in self.classes:
            self.__resolve_class_ref(clasz)

    def __find_fun_by_ref(self, class_id: str, fun_id: str) -> PyFunc:
        idx: str = self.class_keys.index(class_id)

        for fun in self.classes[idx].funs:
            if fun.identifier == fun_id:
                return fun
        return None

    def __var_contains_assign(self, var: str, node) -> bool:
        """Verifies if an AS(sub-)Tree contains assignment to the variable 'var'.
        This could be used to verify if a function, updates it's internal state (or is read-only).

        :param var: the var to check for assignment.
        :param node: the AST.
        :return:
        """
        for child_node in ast.walk(node):
            if (
                isinstance(child_node, ast.Assign)
                or isinstance(child_node, ast.AnnAssign)
                or isinstance(child_node, ast.AugAssign)
            ):
                target = (
                    child_node.targets[0]
                    if isinstance(child_node, ast.Assign)
                    else child_node.target
                )
                if isinstance(target, ast.Name) and target.id == var:
                    return True
                elif isinstance(target, ast.Tuple) and len(
                    [
                        x.id
                        for x in target.elts
                        if isinstance(x, ast.Name) and x.id == var
                    ]
                ):
                    return True
        return False

    def __resolve_class_ref(self, clasz: PyClass):
        for fun in clasz.funs:
            # Get class dependencies through
            for param in fun.args:
                if param.type in self.class_keys:
                    idx = self.class_keys.index(param.type)

                    ref: PyClassRef = PyClassRef(self.class_keys[idx])
                    param.type = PyClassRef(self.class_keys[idx])
                    fun.class_dependency.append(ref)

            for body_node in ast.walk(fun._ast):
                if isinstance(body_node, ast.Call):
                    if isinstance(body_node.func, ast.Attribute):  ## Call on attribute.
                        attr: ast.Attribute = body_node.func
                        fun_identifier: str = attr.attr

                        if not isinstance(attr.value, ast.Name):
                            logging.warning(
                                f"Expected a simple instance reference in the form of ast.Name, but got {attr.value}."
                            )
                            continue

                        clasz_var_identifier: str = attr.value.id
                        class_ref: PyClassRef = fun.find_class_reference_by_var(
                            clasz_var_identifier
                        )

                        ## TODO Check if function ref actually exists
                        fun_ref: PyFuncRef = PyFuncRef(
                            class_ref,
                            fun_identifier,
                            write_state=self.__find_fun_by_ref(
                                class_ref.identifier, fun_identifier
                            ).write_state,
                        )
                        fun.fun_dependency.append(fun_ref)

                    elif isinstance(
                        body_node.func, ast.Name
                    ):  ## Call probably on stateless fun
                        pass


# logging.root.setLevel(logging.NOTSET)
