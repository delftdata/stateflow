import asyncio
import time
import random

from universalis.common.stateflow_ingress import IngressTypes
from universalis.universalis import Universalis
import demo_ycsb
from demo_ycsb import YCSBEntity, stateflow
from stateflow.client.universalis_client import UniversalisClient
from stateflow.runtime.universalis.universalis_runtime import UniversalisRuntime
from zipfian_generator import ZipfGenerator

UNIVERSALIS_HOST: str = 'localhost'
UNIVERSALIS_PORT: int = 8886
KAFKA_URL = 'localhost:9093'
N_ENTITIES = 100
keys: list[int] = list(range(N_ENTITIES))
STARTING_AMOUNT = 100
N_TASKS = 1000
WORKLOAD = 'a'


async def main():

    # Initialize the zipf generator
    zipf_gen = ZipfGenerator(items=N_ENTITIES)
    operations = ["r", "u", "t"]
    operation_mix_a = [0.5, 0.5, 0.0]
    operation_mix_b = [0.95, 0.05, 0.0]
    operation_mix_t = [0.0, 0.0, 1.0]

    if WORKLOAD == 'a':
        operation_mix = operation_mix_a
    elif WORKLOAD == 'b':
        operation_mix = operation_mix_b
    else:
        operation_mix = operation_mix_t

    # Initialize stateflow
    flow = stateflow.init()

    universalis_interface = Universalis(UNIVERSALIS_HOST, UNIVERSALIS_PORT,
                                        ingress_type=IngressTypes.KAFKA,
                                        kafka_url=KAFKA_URL)

    runtime: UniversalisRuntime = UniversalisRuntime(flow,
                                                     universalis_interface,
                                                     "Stateflow",
                                                     n_partitions=6)

    universalis_operators = await runtime.run((demo_ycsb, ))

    print(universalis_operators.keys())

    flow = stateflow.init()
    client: UniversalisClient = UniversalisClient(flow=flow,
                                                  universalis_client=universalis_interface,
                                                  kafka_url=KAFKA_URL,
                                                  operators=universalis_operators)

    time.sleep(1)

    client.wait_until_healthy(timeout=1)

    entities: dict[int, YCSBEntity] = {}
    print("Creating the entities...")
    for i in keys:
        print(f'Creating: {i}')
        entities[i] = YCSBEntity(str(i), STARTING_AMOUNT).get()

    client.stop_consumer_thread()

    operation_counts: dict[str, int] = {"r": 0, "u": 0, "t": 0}
    time.sleep(10)
    client.start_result_consumer_process()
    time.sleep(10)

    for i in range(N_TASKS):
        key = keys[next(zipf_gen)]
        op = random.choices(operations, weights=operation_mix, k=1)[0]
        operation_counts[op] += 1
        if op == "r":
            entities[key].read()
        elif op == "u":
            entities[key].update(STARTING_AMOUNT)
        else:
            key2 = keys[next(zipf_gen)]
            while key2 == key:
                key2 = keys[next(zipf_gen)]
            entities[key].transfer(1, entities[key2])

    client.store_request_csv()
    print(operation_counts)
    time.sleep(10)
    print("Stopping")
    client.stop_result_consumer_process()
    print("Done")

asyncio.run(main())
