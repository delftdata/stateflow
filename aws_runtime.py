from src.runtime.aws.AWSLambdaRuntime import AWSLambdaRuntime
from demo_common import stateflow


flow = stateflow.init()
print("Called init code!")

handler = AWSLambdaRuntime.get_handler(flow)
