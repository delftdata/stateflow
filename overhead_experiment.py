from overhead_experiment_classes import Entity5MB, stateflow
from stateflow.util.local_runtime import LocalRuntime
import time
import pandas as pd

flow = stateflow.init()
# Columns: state size, action, duration (in ms)
# Actions: state (de)serialization, event (de)serialization, routing, actor construction

experiment: pd.DataFrame = pd.DataFrame(
    columns=[
        "EXPERIMENT_ID",
        "REPETITION",
        "STATE_SIZE",
        "STATE_SERIALIZATION_DURATION",
        "EVENT_SERIALIZATION_DURATION",
        "ROUTING_DURATION",
        "ACTOR_CONSTRUCTION",
    ]
)

print(experiment.describe())
client = LocalRuntime(flow, experiment)

total_repetitions = 10000

print(f"Now running experiment with 5MB and {total_repetitions} repetitions.")
entity: Entity5MB = Entity5MB()

client.enable_experiment_mode()
client.set_experiment_id("5MB_one_invocation")
client.set_state_size_experiment("5MB")

start = time.perf_counter()
for x in range(0, total_repetitions):
    client.set_repetition(x)
    entity.execute()

end = time.perf_counter()
print(f"Running 5MB took! {end-start}")
ms_per_thingy = ((end - start) * 1000) / total_repetitions
print(f"Per invocation it took {ms_per_thingy}ms.")


print(experiment.describe())
print(
    experiment[
        [
            "STATE_SERIALIZATION_DURATION",
            "EVENT_SERIALIZATION_DURATION",
            "ROUTING_DURATION",
            "ACTOR_CONSTRUCTION",
        ]
    ].mean()
)

experiment.to_csv("5MB_one_invocation.csv")
