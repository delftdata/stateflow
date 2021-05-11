import pytest
from tests.common.common_classes import stateflow, User, Item
from src.client.kafka_client import StateflowKafkaClient
from src.runtime.beam_runtime import BeamRuntime
import time
from multiprocessing import Process
from threading import Thread
from tests.kafka.KafkaImage import KafkaImage
import uuid
import os


@pytest.fixture(scope="session")
def kafka():
    img = KafkaImage()
    yield img.run()
    img.stop()


def start_runtime():
    flow = stateflow.init()
    run_time = BeamRuntime(flow, timeout=10)
    run_time._setup_pipeline()
    run_time.run()


# @pytest.mark.skip(reason="let's see if this fixes pytest problems")
def test_full_e2e(kafka):
    p = Thread(target=start_runtime, daemon=False)
    p.start()

    flow = stateflow.init()

    time.sleep(5)
    print("Started the runtime!")
    client = StateflowKafkaClient(flow, brokers="localhost:9092")

    user: User = User(str(uuid.uuid4())).get()
    item: Item = Item(str(uuid.uuid4()), 5).get()

    user.update_balance(20).get()
    item.update_stock(4).get()

    initial_balance = user.balance.get()
    initial_stock = item.stock.get()

    buy = user.buy_item(3, item).get()

    final_balance = user.balance.get()
    final_stock = item.stock.get()

    # Killing streaming system.
    # os.kill(p.pid, 9)
    p.join()

    # Kill client.
    client.running = False
    assert buy is True
    assert initial_stock == 4
    assert initial_balance == 20
    assert final_balance == 5
    assert final_stock == 1
