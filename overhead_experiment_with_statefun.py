from overhead_experiment_classes import (
    Entity200KB,
    stateflow,
)
from stateflow.client.kafka_client import StateflowKafkaClient, StateflowClient
import time
from stateflow.client.future import StateflowFailure
import pandas as pd
from stateflow.util import statefun_module_generator


def process_return_event_aws(event, experiment_id, repetition, df) -> pd.DataFrame:
    payload = event.payload

    return_timestamp = payload["OUTGOING_TIMESTAMP"]
    diff = return_timestamp - round(time.time() * 1000)

    to_add = {
        "EXPERIMENT_ID": experiment_id,
        "REPETITION": repetition,
        "STATE_SERIALIZATION_DURATION": payload["STATE_SERIALIZATION_DURATION"],
        "EVENT_SERIALIZATION_DURATION": payload["EVENT_SERIALIZATION_DURATION"],
        "ROUTING_DURATION": payload["ROUTING_DURATION"],
        "ACTOR_CONSTRUCTOR": payload["ACTOR_CONSTRUCTION"],
        # "EXECUTION_GRAPH_TRAVERSAL": payload["EXECUTION_GRAPH_TRAVERSAL"],
        "STATEFUN": payload["STATEFUN"] + diff,
    }
    return df.append(to_add, ignore_index=True)


experiment: pd.DataFrame = pd.DataFrame(
    columns=[
        "EXPERIMENT_ID",
        "REPETITION",
        "STATE_SERIALIZATION_DURATION",
        "EVENT_SERIALIZATION_DURATION",
        "ROUTING_DURATION",
        "ACTOR_CONSTRUCTOR",
        # "EXECUTION_GRAPH_TRAVERSAL",
        "STATEFUN",
    ]
)
flow = stateflow.init()
print(statefun_module_generator.generate(flow))
client: StateflowClient = StateflowKafkaClient(
    flow, brokers="localhost:9092", statefun_mode=True
)
# client.create_all_topics()


repetitions = 100

enitity_future: Entity200KB = Entity200KB()
try:
    entity: Entity200KB = enitity_future.get()
except StateflowFailure:
    entity: Entity200KB = client.find(Entity200KB, "entity200kb").get()
experiment_id = "STATEFUN_200KB"

for i in range(0, repetitions):
    fut = entity.execute()
    fut.get()

    return_event = fut.is_completed
    experiment = process_return_event_aws(return_event, experiment_id, i, experiment)
    print(i)

print(experiment)
experiment.to_csv("statefun_200kb.csv")
