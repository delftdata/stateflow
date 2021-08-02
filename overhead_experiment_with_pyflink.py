from overhead_experiment_classes import (
    EntityExecutionGraph100,
    stateflow,
)
from stateflow.client.kafka_client import StateflowKafkaClient, StateflowClient
import time
from stateflow.client.future import StateflowFailure
import pandas as pd
from stateflow.util import statefun_module_generator


def process_return_event_pyflink(event, experiment_id, repetition, df) -> pd.DataFrame:
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
        "EXECUTION_GRAPH_TRAVERSAL": payload["EXECUTION_GRAPH_TRAVERSAL"],
        "PYFLINK": payload["PYFLINK"] + diff,
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
        "EXECUTION_GRAPH_TRAVERSAL",
        "PYFLINK",
    ]
)
flow = stateflow.init()
client: StateflowClient = StateflowKafkaClient(flow, brokers="localhost:9092")
# client.wait_until_healthy()

repetitions = 100

enitity_future: EntityExecutionGraph100 = EntityExecutionGraph100()
try:
    entity: EntityExecutionGraph100 = enitity_future.get()
except StateflowFailure:
    entity: EntityExecutionGraph100 = client.find(
        EntityExecutionGraph100, "entityexecutiongraph100"
    ).get()
experiment_id = "PYFLINK_500EG"

for i in range(0, repetitions):
    fut = entity.execute(entity)
    fut.get()

    return_event = fut.is_completed
    experiment = process_return_event_pyflink(
        return_event, experiment_id, i, experiment
    )
    print(i)

print(experiment)
experiment.to_csv("pyflink_500eg.csv")
