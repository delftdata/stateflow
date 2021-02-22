from typing import List, Tuple, Any
from collections import OrderedDict


class PyRef:
    def __init__(self, identifier):
        self.identifier = identifier


class PyClassRef(PyRef):
    pass


class PyFuncRef(PyRef):
    def __init__(self, class_ref: PyClassRef, fun_identifier: str):
        self.identifier = class_ref.identifier + "_" + fun_identifier
        self.fun_identifier = fun_identifier
        self.class_identifier = class_ref.identifier


class PyState:
    def __init__(self, identifier: str, keys: List[str], type_map: List[str]):
        self.identifier = identifier
        self.keys = keys
        self.type_map = type_map

    def __str__(self):
        return f"PyState: {self.identifier}, keys: <{self.keys}>, type_map: <{self.type_map}>."


class PyFunc:
    def __init__(self, identifier, args, return_values):
        self.identifier: str = identifier
        self.args: OrderedDict = args
        self.return_values: List[OrderedDict] = return_values
        self.class_dependency: List[PyClassRef] = []
        self.fun_dependency: List[PyFuncRef] = []

    def get_arg_at_pos(self, pos) -> Tuple[str, Any]:
        if (pos - 1) > len(self.args):
            raise AttributeError(
                f"{self.identifier} has only {len(self.args)} arguments."
            )

        i = 0
        for k, v in self.args.items():
            if i == pos:
                return k, v

    def __str__(self):
        return f"PyFunc: {self.identifier}, args: <{self.args}>, return_values: <{self.return_values}>."


class PyClass:
    def __init__(self, identifier, funs: List[PyFunc], state: PyState):
        self.identifier = identifier
        self.funs = funs
        self.state = state

    def __str__(self):
        return f"PyClass: state <{self.state}>, functions: <{self.funs}>."
