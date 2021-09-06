from stateflow.dataflow.dataflow import Dataflow


def generate_operators(flow: Dataflow):
    operators = ",".join(
        [operator.function_type.get_full_name() for operator in flow.operators]
    )
