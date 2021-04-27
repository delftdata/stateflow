import pytest

from tests.common.common_classes import User, stateflow
from src.client.class_ref import (
    MethodRef,
    ClassRef,
    StateflowClient,
    Arguments,
    EventType,
)
from src.dataflow.event import FunctionAddress, FunctionType
from unittest import mock


class TestClassRef:
    def setup(self):
        flow = stateflow.init()
        self.item_desc = stateflow.registered_classes[0].class_desc
        self.user_desc = stateflow.registered_classes[1].class_desc

    def test_method_ref_simple_call(self):
        update_balance_method = self.user_desc.get_method_by_name("update_balance")

        class_ref_mock = mock.MagicMock(ClassRef)
        method_ref = MethodRef("update_balance", class_ref_mock, update_balance_method)

        method_ref(x=1)

        class_ref_mock._invoke_method.assert_called_once()
        name, args = class_ref_mock.invoke_method.call_args[0]

        assert name == "update_balance"
        assert args.get() == {"x": 1}

    def test_method_ref_call_flow(self):
        buy_item_method = self.user_desc.get_method_by_name("buy_item")

        class_ref_mock = mock.MagicMock(ClassRef)
        method_ref = MethodRef("buy_item", class_ref_mock, buy_item_method)

        method_ref(amount=1, item=None)

        class_ref_mock._invoke_flow.assert_called_once()
        flow, args = class_ref_mock.invoke_flow.call_args[0]

        assert isinstance(flow, list)
        assert flow == buy_item_method.flow_list
        assert args.get() == {"amount": 1, "item": None}

    def test_class_ref_simple_invoke(self):
        client_mock = mock.MagicMock(StateflowClient)
        class_ref = ClassRef(
            FunctionAddress(FunctionType("global", "User", True), "test-user"),
            self.user_desc,
            client_mock,
        )

        class_ref._invoke_method("update_balance", Arguments({"x": 1}))

        client_mock.send.assert_called_once()
        event = client_mock.send.call_args[0][0]

        assert event.event_type == EventType.Request.InvokeStateful
        assert event.payload["args"].get() == {"x": 1}
        assert event.payload["method_name"] == "update_balance"
        assert event.fun_address == FunctionAddress(
            FunctionType("global", "User", True), "test-user"
        )

    def test_class_ref_invoke_flow(self):
        client_mock = mock.MagicMock(StateflowClient)
        class_ref = ClassRef(
            FunctionAddress(FunctionType("global", "User", True), "test-user"),
            self.user_desc,
            client_mock,
        )

        class_ref._invoke_flow(
            self.user_desc.get_method_by_name("buy_item").flow_list,
            Arguments({"amount": 1, "item": class_ref}),
        )

        client_mock.send.assert_called_once()
        event = client_mock.send.call_args[0][0]

        assert event.event_type == EventType.Request.EventFlow
        assert event.fun_address == FunctionAddress(
            FunctionType("global", "User", True), "test-user"
        )

        # TODO This test needs to be way more extensive, checking if parameters are properly matched.

    def test_class_ref_test_to_str(self):
        class_ref = ClassRef(
            FunctionAddress(FunctionType("global", "User", True), "test-user"),
            self.user_desc,
            None,
        )

        assert str(class_ref) == "Class reference for User with key test-user."

    def test_class_ref_get_attribute(self):
        client_mock = mock.MagicMock(StateflowClient)
        class_ref = ClassRef(
            FunctionAddress(FunctionType("global", "User", True), "test-user"),
            self.user_desc,
            client_mock,
        )

        class_ref.balance

        client_mock.send.assert_called_once()
        event = client_mock.send.call_args[0][0]

        assert event.event_type == EventType.Request.GetState
        assert event.payload["attribute"] == "balance"
        assert event.fun_address == FunctionAddress(
            FunctionType("global", "User", True), "test-user"
        )

    def test_class_ref_set_attribute(self):
        client_mock = mock.MagicMock(StateflowClient)
        class_ref = ClassRef(
            FunctionAddress(FunctionType("global", "User", True), "test-user"),
            self.user_desc,
            client_mock,
        )

        class_ref.balance = 10

        client_mock.send.assert_called_once()
        event = client_mock.send.call_args[0][0]

        assert event.event_type == EventType.Request.UpdateState
        assert event.payload["attribute"] == "balance"
        assert event.payload["attribute_value"] == 10
        assert event.fun_address == FunctionAddress(
            FunctionType("global", "User", True), "test-user"
        )

    def test_class_ref_get_method_ref(self):
        client_mock = mock.MagicMock(StateflowClient)
        class_ref = ClassRef(
            FunctionAddress(FunctionType("global", "User", True), "test-user"),
            self.user_desc,
            client_mock,
        )

        m_ref = class_ref.update_balance

        assert isinstance(m_ref, MethodRef)
        assert m_ref.method_name == "update_balance"
        assert m_ref.method_desc == self.user_desc.get_method_by_name("update_balance")
        assert m_ref._class_ref == class_ref

    def test_class_ref_get_self_attr(self):
        client_mock = mock.MagicMock(StateflowClient)
        class_ref = ClassRef(
            FunctionAddress(FunctionType("global", "User", True), "test-user"),
            self.user_desc,
            client_mock,
        )

        client_ref = class_ref._client

        assert client_ref == client_mock

    def test_class_ref_get_self_attr_non_existing(self):
        client_mock = mock.MagicMock(StateflowClient)
        class_ref = ClassRef(
            FunctionAddress(FunctionType("global", "User", True), "test-user"),
            self.user_desc,
            client_mock,
        )

        with pytest.raises(AttributeError):
            class_ref._doesnt_exist
