from src.runtime.aws.AWSLambdaRuntime import AWSLambdaRuntime
from demo_common import stateflow

flow = stateflow.init()
runtime: AWSLambdaRuntime = AWSLambdaRuntime(flow)
handler = runtime.get_handler()
