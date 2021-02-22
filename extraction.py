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

        return PyClass(self.identifier, funs, state)

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
        parsed_fun_args: OrderedDict = OrderedDict()
        for i, arg in enumerate(fun_args.args):
            if i == 0 and arg.arg == "self":  # Self arguments are skipped.
                continue

            # Check if there is a type annotation.
            annotation = None
            if arg.annotation is not None:
                annotation = arg.annotation.id

            parsed_fun_args[arg.arg] = annotation

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
        for body_node in ast.walk(fun_node):
            if isinstance(body_node, ast.Return):
                return_value: OrderedDict = self.__parse_return_node(
                    body_node, return_annotations
                )
                if return_value is not None:
                    parsed_return_vals.insert(0, return_value)

        return PyFunc(
            identifier=fun_node.name,
            args=parsed_fun_args,
            return_values=parsed_return_vals,
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

    def resolve(self):
        pass


# logging.root.setLevel(logging.NOTSET)
