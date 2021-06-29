from tests.context import stateflow
from stateflow.wrappers.class_wrapper import (
    ClassWrapper,
    InvocationResult,
    FailedInvocation,
)
from stateflow.analysis.extract_class_descriptor import ExtractClassDescriptor
from stateflow.dataflow.args import Arguments
from stateflow.dataflow.state import State

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


class MoreComplexReturnClass:
    def __init__(self, name: str):
        self.name = name
        self.x = 10

    def update_set_zero(self):
        self.x = 0

        return self.x

    def update_normal_return(self, x: int) -> int:
        self.x -= x
        return self.x

    def update_tuple_return(self, x: int):
        self.x -= x
        return self.x, self.x

    def update_list_return(self, x: int):
        self.x -= x
        return [self.x]

    def update_another(self, x: int):
        self.x -= x
        return ([self.x], self.x)

    def update_empty_return(self, x: int):
        self.x -= x
        return

    def update_no_return(self, x: int):
        self.x -= x

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
        class_desc = ExtractClassDescriptor.create_class_descriptor(extraction)

        return ClassWrapper(SimpleClass, class_desc)

    def complex_wrapper(self) -> ClassWrapper:
        # Parse
        code = inspect.getsource(MoreComplexReturnClass)
        parsed_class = cst.parse_module(code)

        wrapper = cst.metadata.MetadataWrapper(parsed_class)
        expression_provider = wrapper.resolve(cst.metadata.ExpressionContextProvider)

        # Extract
        extraction: ExtractClassDescriptor = ExtractClassDescriptor(
            parsed_class, "MoreComplexReturnClass", expression_provider
        )
        parsed_class.visit(extraction)

        # Create ClassDescriptor
        class_desc = ExtractClassDescriptor.create_class_descriptor(extraction)

        return ClassWrapper(MoreComplexReturnClass, class_desc)

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

        original = getattr(wrapper.cls, "__key__")
        setattr(wrapper.cls, "__key__", ...)

        args = Arguments({"name": "wouter"})
        res = wrapper.init_class(args)
        assert isinstance(res, FailedInvocation)

        setattr(wrapper.cls, "__key__", original)

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

    def test_simple_invoke_return_instance(self):
        wrapper = self.get_wrapper()

        state = State({"name": "wouter", "x": 5})
        args = Arguments({"x": 5})
        result, instance = wrapper.invoke_return_instance("update", state, args)

        assert isinstance(result, InvocationResult)
        assert result.return_results == 0
        assert getattr(instance, "x") == 0
        assert instance.__key__() == "wouter"

    def test_simple_invoke_with_instance(self):
        wrapper = self.get_wrapper()

        state = State({"name": "wouter", "x": 5})
        args = Arguments({"x": 5})
        _, instance = wrapper.invoke_return_instance("update", state, args)

        new_args = Arguments({"x": -7})
        results = wrapper.invoke_with_instance("update", instance, new_args)

        assert results.return_results == 7
        assert results.updated_state["x"] == 7

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
        assert str(result) == result.message

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

    def test_simple_invoke_return_0(self):
        wrapper = self.complex_wrapper()

        state = State({"name": "wouter", "x": 5})
        args = Arguments({})
        result = wrapper.invoke("update_set_zero", state, args)

        assert result.results_as_list()[0] == 0

    def test_returns(self):
        wrapper = self.complex_wrapper()

        state = State({"name": "wouter", "x": 5})
        args = Arguments({"x": 5})

        result = wrapper.invoke("update_normal_return", state, args)
        assert result.results_as_list() == [0]

        result = wrapper.invoke("update_tuple_return", state, args)
        assert result.results_as_list() == [0, 0]

        result = wrapper.invoke("update_list_return", state, args)
        assert result.results_as_list() == [[0]]

        result = wrapper.invoke("update_another", state, args)
        assert result.results_as_list() == [[0], 0]

        result = wrapper.invoke("update_empty_return", state, args)
        assert result.results_as_list() == [None]

        result = wrapper.invoke("update_no_return", state, args)
        assert result.results_as_list() == [None]
