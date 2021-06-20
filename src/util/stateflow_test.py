from pytest import fixture
import pytest
from src.util.local_runtime import LocalRuntime
import src.stateflow as stateflow
import decorator


@fixture(autouse=True)
def stateflow_test():
    client = LocalRuntime(stateflow.init())
    yield client
