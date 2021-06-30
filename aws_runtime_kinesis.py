from stateflow.runtime.aws.kinesis_lambda import AWSKinesisLambdaRuntime
from demo_common import stateflow


flow = stateflow.init()
print("Called init code!")

runtime, handler = AWSKinesisLambdaRuntime.get_handler(flow)
