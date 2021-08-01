from overhead_experiment_classes import Entity100KB, stateflow
from stateflow.client.aws_gateway_client import AWSGatewayClient
import time
from stateflow.client.future import StateflowFailure
import pandas as pd


def process_return_event_aws(event, experiment_id, repetition, df) -> pd.DataFrame:
    payload = event.payload
    to_add = {
        "EXPERIMENT_ID": experiment_id,
        "REPETITION": repetition,
        "STATE_SERIALIZATION_DURATION": payload["STATE_SERIALIZATION_DURATION"],
        "EVENT_SERIALIZATION_DURATION": payload["EVENT_SERIALIZATION_DURATION"],
        "ROUTING_DURATION": payload["ROUTING_DURATION"],
        "ACTOR_CONSTRUCTION": payload["ACTOR_CONSTRUCTION"],
        "KEY_LOCKING": payload["KEY_LOCKING"],
        "READ_STATE": payload["READ_STATE"],
        "WRITE_STATE": payload["WRITE_STATE"],
    }
    return df.append(to_add, ignore_index=True)


experiment: pd.DataFrame = pd.DataFrame(
    columns=[
        "EXPERIMENT_ID",
        "REPETITION",
        "STATE_SERIALIZATION_DURATION",
        "EVENT_SERIALIZATION_DURATION",
        "ROUTING_DURATION",
        "ACTOR_CONSTRUCTION",
        "KEY_LOCKING",
        "READ_STATE",
        "WRITE_STATE",
    ]
)

## AWS LAMBDA
client = AWSGatewayClient(
    stateflow.init(),
    "",
)

repetitions = 100

enitity_future: Entity100KB = Entity100KB()
try:
    entity: Entity100KB = enitity_future.get()
except StateflowFailure:
    entity: Entity100KB = client.find(Entity100KB, "entity100kb").get()
experiment_id = "AWS_100KB"

for i in range(0, repetitions):
    fut = entity.execute()
    fut.get()

    return_event = fut.is_completed
    experiment = process_return_event_aws(return_event, experiment_id, i, experiment)
    print(i)
    time.sleep(2)

print(experiment)
experiment.to_csv("aws_lambda_100kb.csv")
