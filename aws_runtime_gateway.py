from stateflow.runtime.aws.gateway_lambda import AWSGatewayLambdaRuntime
from overhead_experiment_classes import stateflow


flow = stateflow.init()
print("Called init code!")

runtime, handler = AWSGatewayLambdaRuntime.get_handler(flow, gateway=True)
