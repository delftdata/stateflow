import pytest

from src.client import StateflowClient
from src.wrappers.meta_wrapper import MetaWrapper
import inspect
import libcst as cst
from src.analysis.extract_class_descriptor import ExtractClassDescriptor
from src.descriptors.class_descriptor import ClassDescriptor
from src.dataflow.event import EventType
from unittest import mock
from src.client.class_ref import ClassRef


class SimpleClass:
    def __init__(self, name: str):
        self.name = name
        self.x = 10

    def update(self, x: int) -> int:
        self.x -= x
        return self.x

    def __key__(self):
        return self.name


class TestMetaWrapper:
    def get_meta_wrapper(self) -> MetaWrapper:
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

        # Create a meta class..
        meta_class = MetaWrapper(
            str(SimpleClass.__name__),
            tuple(SimpleClass.__bases__),
            dict(SimpleClass.__dict__),
            descriptor=class_desc,
        )

        return meta_class

    def test_initialize(self):
        mock_client = mock.MagicMock(StateflowClient)

        wrapper = self.get_meta_wrapper()
        wrapper.set_client(mock_client)

        # We expect to create a new instance here, by sending an event.
        created_class = wrapper("wouter")

        # Verify the send is called.
        mock_client.send.assert_called_once()

        event, wrapper_ret = mock_client.send.call_args[0]

        assert wrapper == wrapper_ret
        assert event.event_type == EventType.Request.InitClass
        assert not event.fun_address.key
        assert event.fun_address.function_type.name == "SimpleClass"
        assert "args" in event.payload
        assert event.payload["args"]["name"] == "wouter"

    def test_create_class_ref(self):
        mock_client = mock.MagicMock(StateflowClient)

        wrapper = self.get_meta_wrapper()
        wrapper.set_client(mock_client)

        # We expect to create a new instance here, by sending an event.
        created_class = wrapper("wouter", __key="wouter")

        assert isinstance(created_class, ClassRef)
        assert created_class._client == mock_client
        assert created_class._fun_addr.key == "wouter"
