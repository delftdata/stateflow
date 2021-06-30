from stateflow.runtime.aws.gateway_lambda import AWSGatewayLambdaRuntime
from demo_common import stateflow


flow = stateflow.init()
print("Called init code!")

runtime, handler = AWSGatewayLambdaRuntime.get_handler(flow)
