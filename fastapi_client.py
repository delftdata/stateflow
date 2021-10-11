import uuid

from stateflow.client.fastapi.kafka import KafkaFastAPIClient, StateflowFailure
from stateflow.client.fastapi.aws_lambda import AWSLambdaFastAPIClient
from demo_common import stateflow, User

client = KafkaFastAPIClient(stateflow.init())
app = client.get_app()
