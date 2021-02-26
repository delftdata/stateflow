from Function import Function, inspect_return_types
from inspect import getmembers
from inspect import signature
import inspect
from typing import Tuple
import ast
from inspect import Parameter
import astpretty


class statefun:
    def __init__(self, cls):
        self._cls = cls

        print(f"CLASS: {cls.__name__}")
        # Retrieve events.
        print("\t-- EVENTS --")
        for fun in getmembers(cls, predicate=inspect.isfunction):
            signature_of_fun = inspect.signature(fun[1])
            print(f"\tEvent: {fun[0]}")
            print(f"\t\tInput: ")
            for key_param, value_param in signature_of_fun.parameters.items():
                if value_param.name != "self":
                    if value_param.annotation == Parameter.empty:
                        raise AttributeError(
                            f"Method {fun[0]} does not have a type annotation for parameter: {value_param.name}."
                        )
                    print(
                        f"\t\t\t{value_param.name}: {value_param.annotation.__name__}"
                    )
            print(f"\t\tOutput: ")
            print(f"\t\t\t{len(inspect_return_types(fun[1]))} return argument(s)")
            print()

        # Retrieve state
        print("\t-- STATE --")
        state = {}
        cls_ast = ast.parse(inspect.getsource(cls))
        # astpretty.pprint(cls_ast)
        for node in ast.walk(cls_ast):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                    ):
                        if target.attr not in state:
                            state[target.attr] = None
            if isinstance(node, ast.AnnAssign):
                target = node.target
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    state[target.attr] = node.annotation.id

        for state_key, state_v in state.items():
            if state_v:
                print(f"\t{state_key}: {state_v}")
            else:
                print(f"\t{state_key}")

    def __call__(self, *args, **kwargs):
        return Function(self._cls, {}, "", args)


def stateless_fun(balance):
    return balance + 10
