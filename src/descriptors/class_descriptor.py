from src.dataflow.state import StateDescriptor
from typing import List, Optional
from src.descriptors.method_descriptor import MethodDescriptor


class ClassDescriptor:
    """A description of a class method."""

    def __init__(
        self,
        class_name: str,
        state_desc: StateDescriptor,
        methods_dec: List[MethodDescriptor],
    ):
        self.class_name: str = class_name
        self.state_desc: StateDescriptor = state_desc
        self.methods_dec: List[MethodDescriptor] = methods_dec

    def get_method_by_name(self, name: str) -> Optional[MethodDescriptor]:
        filter = [desc for desc in self.methods_dec if desc.method_name == name]

        if len(filter) == 0:
            return None

        return filter[0]

    def link_to_other_classes(self, descriptors: List["ClassDescriptor"]):
        for method in self.methods_dec:
            method.link_to_other_classes(descriptors)
