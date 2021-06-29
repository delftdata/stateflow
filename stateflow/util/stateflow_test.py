from pytest import fixture
from stateflow.util.local_runtime import LocalRuntime
import stateflow.core as stateflow


@fixture(autouse=True)
def stateflow_test():
    client = LocalRuntime(stateflow.init())
    yield client
