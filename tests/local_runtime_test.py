from .context import stateflow


from stateflow import stateflow_test
from tests.common.common_classes import User, Item


def test_user():
    user = User("kyriakos")
    user.update_balance(10)

    assert user.balance == 10
    assert user.username == "kyriakos"
