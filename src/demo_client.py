import stateflow
from src.client.future import StateflowFuture
from src.client.kafka_client import StateflowKafkaClient, StateflowClient
from src.runtime.beam_runtime import BeamRuntime
import time


@stateflow.stateflow
class Fun:
    def __init__(self, username: str):
        self.x = 3
        self.username = username

    def update_x(self, delta_x: int) -> int:
        self.x -= delta_x
        return self.x

    def __key__(self):
        return self.username


class Fun2:
    def __init__(self, username: str):
        self.x = 3
        self.username = username

    def update_x(self, delta_x: int) -> int:
        self.x -= delta_x
        return self.x

    def __key__(self):
        return self.username


# Initialize stateflow
flow = stateflow.init()

# Setup the client.
client: StateflowClient = StateflowKafkaClient(flow, brokers="localhost:9092")

# Create a class.


start = time.time()
fun_list = []
for x in range(0, 10000):
    fun: StateflowFuture[Fun] = Fun(f"wouter_{x}")
    fun_list.append(fun)
end = time.time()
client.await_futures(fun_list)
print(f"Non blocking future took {end-start}s")

start = time.time()
for x in range(0, 10000):
    Fun2(f"wouter_{x}")
end = time.time()
print(f"Fun2 took {end-start}s")
