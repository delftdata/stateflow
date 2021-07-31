from overhead_experiment_classes import (
    EntityExecutionGraph10,
    EntityInteractive,
    stateflow,
)
from stateflow.util.local_runtime import LocalRuntime
from stateflow.util.dataflow_visualizer import visualize_flow
import time
import pandas as pd

flow = stateflow.init()
# Columns: state size, action, duration (in ms)
# Actions: state (de)serialization, event (de)serialization, routing, actor construction

experiment: pd.DataFrame = pd.DataFrame(
    columns=[
        "EXPERIMENT_ID",
        "REPETITION",
        "INTERACTIONS",
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

print(f"Now running experiment with 50KB and {total_repetitions} repetitions.")
entities = []
for i in range(0, 15):
    other_entity: EntityExecutionGraph10 = EntityExecutionGraph10(f"entity-{i}")
    entities.append(other_entity)

entity: EntityInteractive = EntityInteractive()

print(visualize_flow(entity._methods["execute"].flow_list))
print(
    f"ExecutionGraph length {len([x for x in entity._methods['execute'].flow_list if x.typ == 'INVOKE_SPLIT_FUN' or x.typ == 'INVOKE_CONDITIONAL'])}."
)

client.enable_experiment_mode()
client.set_experiment_id("ExecutionGraph_interactive_10")
client.set_execution_graph_length(15)

start = time.perf_counter()
total = 0
for x in range(0, total_repetitions):
    if x % 100 == 0:
        print(x)
    client.set_repetition(x)
    total += entity.execute(entities)

print(f"Total is {total}, {total == total_repetitions}")

end = time.perf_counter()
print(f"This took! {end-start}")
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

print(experiment["EVENT_SERIALIZATION_DURATION"].max())
print(experiment["EVENT_SERIALIZATION_DURATION"].sort_values(ascending=False).head(10))

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


experiment.to_csv("interactions_15.csv")
