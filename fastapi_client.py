from src.client.fastapi.FastAPIClient import FastAPIClient
from demo_common import stateflow

client = FastAPIClient(stateflow.init())
app = client.get_app()
