import stateflow
from src.client.future import StateflowFuture
from src.client.kafka_client import StateflowKafkaClient, StateflowClient
from src.runtime.beam_runtime import BeamRuntime
from src.dataflow.event import Event, FunctionType, FunctionAddress, EventType
from src.dataflow.args import Arguments
from typing import Tuple
import time


@stateflow.stateflow
class Fun:
    def __init__(self, username: str):
        self.x = 3
        self.username = username

    def update_x(self, delta_x: int) -> Tuple[int, int]:
        self.x -= delta_x
        return self.x, self.x

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
fun: Fun = Fun("wouter").get()
update_delta: int = fun.update_x(5).get()
print(update_x)
