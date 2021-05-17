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
    flow = stateflow.init()
    run_time = BeamRuntime(flow, timeout=15)
    run_time._setup_pipeline()
    run_time.run()


# @pytest.mark.skip(reason="let's see if this fixes pytest problems")
def test_full_e2e_multiple_splits(kafka):
    try:
        time.sleep(5)
        p = Thread(target=start_runtime, daemon=False)
        p.start()

        flow = stateflow.init()

        print("Started the runtime!")
        client = StateflowKafkaClient(flow, brokers="localhost:9092")
        client.wait_until_healthy()
        print("Started client")

        b: ExperimentalB = ExperimentalB(str(uuid.uuid4())).get(timeout=25)
        a: ExperimentalA = ExperimentalA(str(uuid.uuid4())).get(timeout=5)

        outcome = a.complex_method(10, b).get(timeout=5)
        final_balance_b = b.balance.get(timeout=5)
        final_balance_a = a.balance.get(timeout=5)

        # Kill client.
        client.running = False

        # Killing streaming system.
        p.join()

        assert outcome is True
        assert final_balance_b == 10
        assert final_balance_a == 0

        print("All asserts are correct")
    except Exception as exc:
        print(f"Got an exception {exc}")
        client.running = False
        assert False


def test_full_e2e(kafka):
    try:
        time.sleep(5)
        p = Thread(target=start_runtime, daemon=False)
        p.start()

        flow = stateflow.init()
        print("Started the runtime!")
        client = StateflowKafkaClient(flow, brokers="localhost:9092")
        client.wait_until_healthy()
        print("Started client")

        user: User = User(str(uuid.uuid4())).get(timeout=25)
        item: Item = Item(str(uuid.uuid4()), 5).get(timeout=5)

        user.update_balance(20).get(timeout=5)
        item.update_stock(4).get(timeout=5)

        initial_balance = user.balance.get(timeout=5)
        initial_stock = item.stock.get(timeout=5)

        buy = user.buy_item(3, item).get(timeout=5)

        final_balance = user.balance.get(timeout=5)
        final_stock = item.stock.get(timeout=5)

        # Killing streaming system.
        p.join()

        client.running = False

        assert buy is True
        assert initial_stock == 4
        assert initial_balance == 20
        assert final_balance == 5
        assert final_stock == 1

        print("Finished all asserts :)")
    except Exception as exc:
        print(f"Got an exception {exc}")
        client.running = False
        assert False
