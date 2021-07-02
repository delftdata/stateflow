import uuid

from stateflow.client.fastapi.kafka import KafkaFastAPIClient, StateflowFailure
from demo_common import stateflow, User

client = KafkaFastAPIClient(stateflow.init())
app = client.get_app()


@app.get("/extra")
async def create_users_set_balance(username: str, balance: int):
    try:
        user_one: User = await User(f"{username}-0")
        user_two: User = await User(f"{username}-1")

        await user_one.update_balance(balance)
        await user_two.update_balance(balance)
    except StateflowFailure as exc:
        return exc

    return "Done!"
