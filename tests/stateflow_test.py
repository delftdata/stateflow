import pytest
from tests.common.common_classes import (
    stateflow,
    User,
    Item,
    ExperimentalB,
    ExperimentalA,
)
from src.client.kafka_client import StateflowKafkaClient
from src.runtime.beam_runtime import BeamRuntime
import time
from multiprocessing import Process
from threading import Thread
from tests.kafka.KafkaImage import KafkaImage
import uuid
from src.util import dataflow_visualizer
from src.dataflow.address import FunctionType
import os


@pytest.fixture(scope="session")
def kafka():
    img = KafkaImage()
    yield img.run()
    img.stop()


def start_runtime():
    try:
        run_time = BeamRuntime(stateflow.init(), timeout=15)
        run_time._setup_pipeline()
        run_time.run()
    except Exception as excp:
        print(f"Got an exception. {excp}")
        raise RuntimeError("Exception!")


@pytest.fixture(scope="session")
def start_and_stop(kafka):
    try:
        time.sleep(5)
        flow = stateflow.init()
        p = Thread(target=start_runtime, daemon=False)
        p.start()

        print("Started the runtime!")
        client = StateflowKafkaClient(flow, brokers="localhost:9092")
        client.wait_until_healthy()
        print("Started client")

        yield client

        # Will be executed after the last test
        client.running = False
        p.join()
    except Exception as excp:
        raise RuntimeError(f"Exception! {excp}")


# @pytest.mark.usefixtures("kafka")
class TestE2E:
    # @pytest.mark.skip(reason="let's see if this fixes pytest problems")
    def test_full_e2e_multiple_splits(self, start_and_stop):
        try:
            b: ExperimentalB = ExperimentalB(str(uuid.uuid4())).get(timeout=25)
            a: ExperimentalA = ExperimentalA(str(uuid.uuid4())).get(timeout=5)

            outcome = a.complex_method(10, b).get(timeout=5)
            final_balance_b = b.balance.get(timeout=5)
            final_balance_a = a.balance.get(timeout=5)

            assert outcome is True
            assert final_balance_b == 10
            assert final_balance_a == 0

            print("All asserts are correct")
        except Exception as exc:
            print(f"Got an exception {exc}")
            assert False

    def test_simple_if(self, start_and_stop):
        b: ExperimentalB = ExperimentalB(str(uuid.uuid4())).get(timeout=25)
        a: ExperimentalA = ExperimentalA(str(uuid.uuid4())).get(timeout=5)

        outcome_0 = a.complex_if(11, b).get(timeout=5)
        b_balance = b.balance.get()

        assert outcome_0 == 0
        assert b_balance == 11

        # 2nd scenario
        b.balance = 5
        b_balance = b.balance.get()
        outcome_1 = a.complex_if(9, b).get(timeout=5)

        assert outcome_1 == 1
        assert b_balance == 5

        b.balance = 0
        b_balance = b.balance.get()
        outcome_2 = a.complex_if(9, b).get(timeout=5)

        assert outcome_2 == 2
        assert b_balance == 0

    def test_full_e2e(self, start_and_stop):
        try:
            user: User = User(str(uuid.uuid4())).get(timeout=25)
            item: Item = Item(str(uuid.uuid4()), 5).get(timeout=5)

            user.update_balance(20).get(timeout=5)
            item.update_stock(4).get(timeout=5)

            initial_balance = user.balance.get(timeout=5)
            initial_stock = item.stock.get(timeout=5)

            buy = user.buy_item(3, item).get(timeout=5)

            final_balance = user.balance.get(timeout=5)
            final_stock = item.stock.get(timeout=5)

            assert buy is True
            assert initial_stock == 4
            assert initial_balance == 20
            assert final_balance == 5
            assert final_stock == 1

            print("Finished all asserts :)")
        except Exception as exc:
            print(f"Got an exception {exc}")
            assert False
