import pytest

from tests.common.common_classes import User, stateflow
from src.client.class_ref import MethodRef, ClassRef
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

        class_ref_mock.invoke_method.assert_called_once()
        name, args = class_ref_mock.invoke_method.call_args[0]

        assert name == "update_balance"
        assert args.get() == {"x": 1}

    def test_method_ref_call_flow(self):
        buy_item_method = self.user_desc.get_method_by_name("buy_item")

        class_ref_mock = mock.MagicMock(ClassRef)
        method_ref = MethodRef("buy_item", class_ref_mock, buy_item_method)

        method_ref(amount=1, item=None)

        class_ref_mock.invoke_flow.assert_called_once()
        flow, args = class_ref_mock.invoke_flow.call_args[0]

        assert isinstance(flow, list)
        assert flow == buy_item_method.flow_list
        assert args.get() == {"amount": 1, "item": None}
