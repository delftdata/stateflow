from typing import List, Tuple, Any
from collections import OrderedDict


class PyRef:
    def __init__(self, identifier):
        self.identifier = identifier

    def __str__(self):
        return self.identifier


class PyClassRef(PyRef):
    pass


class PyFuncRef(PyRef):
    def __init__(
        self, class_ref: PyClassRef, fun_identifier: str, write_state: bool = True
    ):
        self.identifier = class_ref.identifier + "_" + fun_identifier
        self.fun_identifier = fun_identifier
        self.class_identifier = class_ref.identifier
        self.write_state = write_state


class PyState:
    def __init__(self, identifier: str, keys: List[str], type_map: List[str]):
        self.identifier = identifier
        self.keys = keys
        self.type_map = type_map

    def __str__(self):
        return f"PyState: {self.identifier}, keys: <{self.keys}>, type_map: <{self.type_map}>."


class PyParam:
    def __init__(self, name: str, type: Any):
        self.name = name
        self.type = type


class PyFunc:
    def __init__(self, identifier, args, return_values, write_state, ast):
        self.identifier: str = identifier
        self.args: List[PyParam] = args
        self.return_values: List[OrderedDict] = return_values
        self.write_state = write_state
        self._ast = ast

        self.class_dependency: List[PyClassRef] = []
        self.fun_dependency: List[PyFuncRef] = []

        print(f"I'm {self.identifier} and I have {self.write_state} writes.")

    def find_class_reference_by_var(self, var: str) -> PyClassRef:
        for param in self.args:
            if param.name == var:
                return param.type
        raise AttributeError(
            f"Could not find PyClassRef for variable {var}. Probably, there went something wrong in extracting class references."
        )

    def only_read_class_reference(self, class_ref: PyClassRef) -> bool:
        # Right now, that a classref is read only iff there are _no_ function calls.
        # Otherwise it's write as well. Obviously this is very naive e.g. item.price = ..
        # We need to fix this later
        for fun in self.fun_dependency:
            if fun.class_identifier == class_ref.identifier:
                return False
        return True

    def get_arg_at_pos(self, pos) -> PyParam:
        if (pos - 1) > len(self.args):
            raise AttributeError(
                f"{self.identifier} has only {len(self.args)} arguments."
            )

        i = 0
        for param in self.args:
            if i == pos:
                return param
            i += 1

    def __str__(self):
        return f"PyFunc: {self.identifier}, args: <{self.args}>, return_values: <{self.return_values}>."


class PyClass:
    def __init__(self, identifier, funs: List[PyFunc], state: PyState, ast):
        self.identifier = identifier
        self.funs = funs
        self.state = state
        self._ast = ast

    def __str__(self):
        return f"PyClass: state <{self.state}>, functions: <{self.funs}>."
