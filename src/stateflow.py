from runtime.runtime import Runtime
from inspect import isclass, getsource
import libcst as cst
from typing import List
from src.descriptors import ClassDescriptor
from src.wrappers import ClassWrapper
from src.analysis.extract_class_descriptor import ExtractClassDescriptor

registered_class: List[ClassWrapper] = []


def stateflow(cls):
    if not isclass(cls):
        raise AttributeError(f"Expected a class but got an {cls}.")

    # Parse
    class_source = getsource(cls)
    parsed_class = cst.parse_module(class_source)

    # Extract
    extraction: ExtractClassDescriptor = ExtractClassDescriptor(parsed_class)
    parsed_class.visit(extraction)

    # Create ClassDescriptor
    class_desc: ClassDescriptor = ExtractClassDescriptor.create_class_descriptor(
        extraction
    )

    # Register the class.
    registered_class.append(ClassWrapper(cls, class_desc))


class StateFlow:
    def __init__(self, runtime: Runtime):
        self.runtime = runtime

    def run(self):
        self.runtime.run()
