import pytest
from tests.common.common_classes import (
    stateflow,
    User,
    Item,
    ExperimentalB,
    ExperimentalA,
)
from src.client.kafka_client import StateflowKafkaClient
from src.runtime.flink_runtime import FlinkRuntime
from src.runtime.beam_runtime import BeamRuntime
from src.serialization.pickle_serializer import PickleSerializer

import time
from multiprocessing import Process
from threading import Thread
from tests.kafka.KafkaImage import KafkaImage
import uuid
from src.util import dataflow_visualizer
from src.dataflow.address import FunctionType
import os


@pytest.fixture(scope="class")
def kafka():
    img = KafkaImage()
    yield img.run()
    img.stop()


def start_runtime(runtime):
    try:
        if runtime == "beam":
            run_time = BeamRuntime(stateflow.init(), timeout=15, serializer=PickleSerializer())
        else:
            run_time = FlinkRuntime(stateflow.init(), serializer=PickleSerializer())
        run_time.run(async_execution=True)
    except Exception as excp:
        print(f"Got an exception. {excp}", flush=True)
        raise RuntimeError("Exception!")


@pytest.fixture(scope="class")
def start_and_stop(kafka, request):
    try:
        time.sleep(5)
        flow = stateflow.init()
        if request.param == "beam":
            p = Thread(target=start_runtime, args=(request.param,), daemon=False)
            p.start()
        else:
            start_runtime(request.param)

        print("Started the runtime!")
        client = StateflowKafkaClient(flow, brokers="localhost:9092", serializer=PickleSerializer())
        client.wait_until_healthy()
        print("Started client")

        yield client

        # Will be executed after the last test
        client.running = False
        if request.param == "beam":
            p.join()
    except Exception as excp:
        raise RuntimeError(f"Exception! {excp}")


@pytest.mark.parametrize("start_and_stop", ["beam", "flink"], indirect=True)
class TestE2E:
    # @pytest.mark.skip(reason="let's see if this fixes pytest problems")
    #@pytest.mark.parametrize("start_and_stop", ["beam", "flink"], indirect=True)
    def test_full_e2e_multiple_splits(self, start_and_stop):
        try:
            b: ExperimentalB = ExperimentalB(str(uuid.uuid4())).get(timeout=25)
            a: ExperimentalA = ExperimentalA(str(uuid.uuid4())).get(timeout=10)

            outcome = a.complex_method(10, b).get(timeout=10)
            final_balance_b = b.balance.get(timeout=10)
            final_balance_a = a.balance.get(timeout=10)

            assert outcome is True
            assert final_balance_b == 10
            assert final_balance_a == 0

            a.work_with_list(1, [b]).get(timeout=10)
            final_balance_b = b.balance.get(timeout=10)
            assert final_balance_b == 30

            a.work_with_list(0, [b]).get(timeout=10)
            final_balance_b = b.balance.get(timeout=10)
            assert final_balance_b == 30

            print("All asserts are correct")
        except Exception as exc:
            print(f"Got an exception {exc}")
            assert False

    #@pytest.mark.parametrize("start_and_stop", ["beam", "flink"], indirect=True)
    def test_simple_if(self, start_and_stop):
        b: ExperimentalB = ExperimentalB(str(uuid.uuid4())).get(timeout=25)
        a: ExperimentalA = ExperimentalA(str(uuid.uuid4())).get(timeout=10)

        outcome_0 = a.complex_if(11, b).get(timeout=10)
        b_balance = b.balance.get(timeout=10)

        assert outcome_0 == 0
        assert b_balance == 11

        # 2nd scenario
        b.balance = 5
        b_balance = b.balance.get(timeout=10)
        outcome_1 = a.complex_if(9, b).get(timeout=10)

        assert outcome_1 == 1
        assert b_balance == 5

        b.balance = 0
        b_balance = b.balance.get(timeout=10)
        outcome_2 = a.complex_if(9, b).get(timeout=10)

        assert outcome_2 == 2
        assert b_balance == 0

        b.balance = 0
        b_balance = b.balance.get(timeout=10)
        outcome_3 = a.more_complex_if(-3, b).get(timeout=10)

        assert outcome_3 == -3
        assert b_balance == 0

        b.balance = 4
        b_balance = b.balance.get(timeout=10)
        outcome_4 = a.more_complex_if(2, b).get(timeout=10)

        assert b_balance == 4
        assert outcome_4 == 1

        b.balance = 4
        b_balance = b.balance.get(timeout=10)
        outcome_5 = a.more_complex_if(3, b).get(timeout=10)

        assert outcome_5 == -1
        assert b_balance == 4

        b.balance = 0
        b.balance.get(timeout=10)
        a.balance = 0
        a.balance.get(timeout=10)
        outcome_6 = a.test_no_return(6, b).get(timeout=10)
        b_balance = b.balance.get(timeout=10)
        a_balance = a.balance.get(timeout=10)

        assert b_balance == 6
        assert outcome_6 is None
        assert a_balance == 0

    #@pytest.mark.parametrize("start_and_stop", ["flink", "beam"], indirect=True)
    def test_full_e2e(self, start_and_stop):
        try:
            import src.util.dataflow_visualizer as viz

            viz.visualize_flow(
                stateflow.registered_classes[1]
                .class_desc.get_method_by_name("buy_item")
                .flow_list
            )

            user: User = User(str(uuid.uuid4())).get(timeout=25)
            item: Item = Item(str(uuid.uuid4()), 5).get(timeout=10)

            user.update_balance(20).get(timeout=10)
            item.update_stock(4).get(timeout=10)

            initial_balance = user.balance.get(timeout=10)
            initial_stock = item.stock.get(timeout=10)

            buy = user.buy_item(3, item).get(timeout=10)

            final_balance = user.balance.get(timeout=10)
            final_stock = item.stock.get(timeout=10)

            assert buy is True
            assert initial_stock == 4
            assert initial_balance == 20
            assert final_balance == 5
            assert final_stock == 1

            print("Finished all asserts :)")
        except Exception as exc:
            print(f"Got an exception {exc}")
            assert False

    #@pytest.mark.parametrize("start_and_stop", ["beam", "flink"], indirect=True)
    def test_for_loop(self, start_and_stop):
        try:
            b: ExperimentalB = ExperimentalB(str(uuid.uuid4())).get(timeout=25)
            b_2: ExperimentalB = ExperimentalB(str(uuid.uuid4())).get(timeout=25)
            a: ExperimentalA = ExperimentalA(str(uuid.uuid4())).get(timeout=10)

            return_a = a.for_loops(0, [b, b_2]).get(timeout=10)
            b_balance = b.balance.get(timeout=10)
            b2_balance = b_2.balance.get(timeout=10)

            assert return_a == -1
            assert b_balance == 5
            assert b2_balance == 5

            return_a = a.for_loops(4, [b, b_2]).get(timeout=10)
            b_balance = b.balance.get(timeout=10)
            b2_balance = b_2.balance.get(timeout=10)

            assert return_a == 4
            assert b_balance == 10
            assert b2_balance == 10
            print("Finished all asserts :)")
        except Exception as exc:
            print(f"Got an exception {exc}")
            assert False
