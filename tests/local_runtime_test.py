from .context import stateflow
from stateflow.util.stateflow_test import stateflow_test
from tests.common.common_classes import User, Item


def test_user():
    user = User("kyriakos")
    user.update_balance(10)

    assert user.balance == 10
