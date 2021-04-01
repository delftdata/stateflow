from dataflow import FunctionType
from descriptors import ClassDescriptor, MethodDescriptor
from concurrent.futures import Future


class MethodRef:
    def __init__(
        self, method_name: str, class_ref: "ClassRef", method_des: MethodDescriptor
    ):
        self.method_name = method_name
        self._class_ref = class_ref

    def __call__(self, *args, **kwargs):
        print(
            f"Now invoking method: {self.method_name}, with arguments: {args} and {kwargs}."
        )


class ClassRef:
    def __init__(self, fun_type: FunctionType, class_desc: ClassDescriptor):
        self._fun_type = fun_type
        self._class_desc = class_desc
        self._attributes = list(class_desc.state_desc.get_keys())
        self._methods = {
            method.method_name: method for method in class_desc.methods_dec
        }

    def _invoke_method(self, handle: str, arguments):
        pass

    def _get_attribute(self, attr: str) -> Future:
        pass

    def _set_attribute(self, attr: str, new):
        pass

    def __getattr__(self, item):
        if item in self._attributes:
            print(f"Attribute access: {item}")

        if item in self._methods.keys():
            print(f"Method invocation: {item}")
            return MethodRef(item, self, self._methods[item])

    def __str__(self):
        return f"Class reference for {self._fun_type.name}."
