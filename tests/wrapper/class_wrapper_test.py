import pytest
from src.wrappers import ClassWrapper, InvocationResult, FailedInvocation
from src.analysis.extract_class_descriptor import ExtractClassDescriptor
from src.analysis.extract_method_descriptor import ExtractMethodDescriptor
from src.descriptors import ClassDescriptor
from src.dataflow.args import Arguments
from src.dataflow.state import State

import inspect
import libcst as cst


class SimpleClass:
    def __init__(self, name: str):
        self.name = name
        self.x = 10

    def update(self, x: int) -> int:
        self.x -= x
        return self.x

    def __key__(self):
        return self.name


class TestClassWrapper:
    def get_wrapper(self) -> ClassWrapper:
        # Parse
        code = inspect.getsource(SimpleClass)
        parsed_class = cst.parse_module(code)

        wrapper = cst.metadata.MetadataWrapper(parsed_class)
        expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

        # Extract
        extraction: ExtractClassDescriptor = ExtractClassDescriptor(
            parsed_class, "SimpleClass", expression_provider
        )
        parsed_class.visit(extraction)

        # Create ClassDescriptor
        class_desc: ClassDescriptor = ExtractClassDescriptor.create_class_descriptor(
            extraction
        )

        return ClassWrapper(SimpleClass, class_desc)

    def test_simple_init_method(self):
        wrapper = self.get_wrapper()

        args = Arguments({"name": "wouter"})
        res = wrapper.init_class(args)
        assert isinstance(res, InvocationResult)
        assert res.return_results[0] == "wouter"
        assert res.updated_state.get() == {"name": "wouter", "x": 10}

    def test_simple_init_wrong_args(self):
        wrapper = self.get_wrapper()

        args = Arguments({"wrong": "jsj"})
        res = wrapper.init_class(args)
        assert isinstance(res, FailedInvocation)

    def test_simple_init_error_during_invocation(self):
        wrapper = self.get_wrapper()

        setattr(wrapper.cls, "__key__", ...)

        args = Arguments({"name": "wouter"})
        res = wrapper.init_class(args)
        assert isinstance(res, FailedInvocation)

    def test_unknown_method(self):
        assert self.get_wrapper().find_method("UNKNOWN") is None

    def test_str_repr(self):
        assert str(self.get_wrapper()) == "ClassWrapper for the class SimpleClass."

    def test_simple_invoke(self):
        wrapper = self.get_wrapper()

        state = State({"name": "wouter", "x": 5})
        args = Arguments({"x": 5})
        result = wrapper.invoke("update", state, args)

        assert isinstance(result, InvocationResult)
        assert result.return_results == 0
        assert result.updated_state.get() == {"name": "wouter", "x": 0}

    def test_simple_invoke_argument_mismatch(self):
        wrapper = self.get_wrapper()

        state = State({"name": "wouter", "x": 5})
        args = Arguments({"y": 5})
        result = wrapper.invoke("update", state, args)

        assert isinstance(result, FailedInvocation)

    def test_simple_invoke_state_mismatch(self):
        wrapper = self.get_wrapper()

        state = State({"noname": "wouter"})
        args = Arguments({"x": 5})
        result = wrapper.invoke("update", state, args)

        assert isinstance(result, FailedInvocation)

    def test_simple_invoke_failed(self):
        wrapper = self.get_wrapper()

        setattr(wrapper.cls, "update", ...)

        state = State({"name": "wouter", "x": 5})
        args = Arguments({"x": 5})
        result = wrapper.invoke("update", state, args)

        assert isinstance(result, FailedInvocation)

    def test_simple_invoke_unknown_method(self):
        wrapper = self.get_wrapper()

        state = State({"name": "wouter", "x": 5})
        args = Arguments({"x": 5})
        result = wrapper.invoke("notexist", state, args)

        assert isinstance(result, FailedInvocation)
