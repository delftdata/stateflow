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

    def update_x(self, delta_x: int) -> int:
        self.x -= delta_x
        return self.x

    def __key__(self):
        return self.username


# Initialize stateflow
flow = stateflow.init()

# Setup the client.
client: StateflowClient = StateflowKafkaClient(flow, brokers="localhost:9092")

print("---")
fun: Fun = Fun("wouter").get()
print(fun)

print(f"update_result: {fun.update_x(-3).get()}")


fun.x = 10
new_x: StateflowFuture = fun.x

print(f"New value for x: {new_x.get()}")
print("---")
