import inspect
import ast
from textwrap import dedent
from inspect import Parameter


class Function:
    def __init__(self, cls, events, state, *args):
        self._obj = cls(args)
        self.name = cls.__name__
        self.events = events
        self.state = state

        print(self.events)

    def __getattr__(self, item):
        # IF STATE RETURN DIRECT OBJECT
        # IF NOT STATE RETURN CALL EVENT
        # print(type(item))
        # return CallEvent(self, item)
        return self._obj.__getattribute__(item)

    def __str__(self):
        return f"Function of type {self.name}"


class State:
    def __init__(self, id, keys, value_map, type_map):
        assert len(keys) == len(value_map) == len(type_map)

        self.id = id
        self.keys = keys
        self.value_map = value_map
        self.type_map = type_map

    def exists(self, key):
        if key not in self.keys:
            return False
        return True

    def get_type(self, key):
        if self.exists(key):
            raise AttributeError(f"{key} does not exist in state of {self.id}")
        return self.type_map[key]

    def get(self, key):
        if self.exists(key):
            raise AttributeError(f"{key} does not exist in state of {self.id}")
        return self.value_map[key]

    def put(self, key, value):
        if self.exists(key):
            raise AttributeError(f"{key} does not exist in state of {self.id}")
        self.value_map[key] = value


class CallEvent:
    def __init__(self, fun, event):
        self.fun = fun
        self.event = event

    def __call__(self, *args, **kwargs):
        print(f"Called event {self.event} {args}")
        return self.fun._obj.__getattribute__(self.event)(*args)


def inspect_return_types(fun):
    if not inspect.isfunction(fun):
        raise AttributeError(f"Expected function but got {fun}.")

    # Obtain amount of return elements.
    return_list = []
    for ast_el in ast.walk(ast.parse(dedent(inspect.getsource(fun)))):
        if type(ast_el) == ast.Return:
            return_list.insert(0, parse_return_node(ast_el))
    # Obtain return type annotations.
    fun_annotate = inspect.signature(fun)
    # if fun_annotate.return_annotation != Parameter.empty:
    # print(fun_annotate.return_annotation)
    # print(fun_annotate.return_annotation.__name__)

    if len(return_list) == 1:
        return return_list[0]
    return return_list


def parse_return_node(node):
    if not type(node) == ast.Return:
        raise AttributeError(f"Expected ast.Return but got {node}.")

    value = node.value
    if value is None:
        return None
    elif type(value) == ast.Tuple:
        print("HERE")
        return [f"return_argument_{i}" for i, _ in enumerate(value.elts)]
    else:
        return ["return_argument_0"]
