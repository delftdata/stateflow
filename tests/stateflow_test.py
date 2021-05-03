import pytest
from tests.common.common_classes import User, stateflow, Item
from src.client.kafka_client import StateflowKafkaClient
from src.runtime.beam_runtime import BeamRuntime
import time
from multiprocessing import Process
from tests.kafka.KafkaImage import KafkaImage


@pytest.fixture(scope="session")
def kafka():
    img = KafkaImage()
    yield img.run()
    img.stop()


def start_runtime(flow):
    BeamRuntime(flow, test_mode=True).run()


@pytest.mark.timeout(40)
def test_full_e2e(kafka):
    flow = stateflow.init()

    p = Process(target=start_runtime, args=(flow,))
    p.start()
    time.sleep(5)
    print("Started the runtime!")
    client = StateflowKafkaClient(flow, brokers="localhost:9092")

    user: User = User("wouter").get()
    item: Item = Item("coke", 5).get()

    user.update_balance(20).get()
    item.update_stock(3).get()

    buy = user.buy_item(3, item).get()

    assert buy is True
    assert user.balance.get() == 5
    assert item.stock.get() == 0

    p.join(1)
    p.terminate()
