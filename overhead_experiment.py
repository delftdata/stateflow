from overhead_experiment_classes import EntityExecutionGraph10, stateflow
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
        "EXECUTION_GRAPH_TRAVERSAL",
    ]
)

print(experiment.describe())
client = LocalRuntime(flow, experiment)

total_repetitions = 10000

print(f"Now running experiment with 5MB and {total_repetitions} repetitions.")
entity: EntityExecutionGraph10 = EntityExecutionGraph10()

client.enable_experiment_mode()
client.set_experiment_id("ExecutionGraph_length_10")
client.set_state_size_experiment("500KB")

start = time.perf_counter()
for x in range(0, total_repetitions):
    client.set_repetition(x)
    print(entity.execute())

end = time.perf_counter()
print(f"Running ExecutionGraph length 10 took! {end-start}")
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
            "EXECUTION_GRAPH_TRAVERSAL",
        ]
    ].mean()
)

print(
    experiment[
        [
            "STATE_SERIALIZATION_DURATION",
            "EVENT_SERIALIZATION_DURATION",
            "ROUTING_DURATION",
            "ACTOR_CONSTRUCTION",
            "EXECUTION_GRAPH_TRAVERSAL",
        ]
    ].std()
)


# experiment.to_csv("500.csv")
