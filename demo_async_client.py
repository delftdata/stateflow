from demo_common import User, Item, stateflow
from src.client.async.async_kafka_client import StateflowKafkaClient
from src.dataflow.event import Event, EventType
from src.dataflow.address import FunctionAddress, FunctionType
from src.dataflow.args import Arguments
import asyncio


async def main():
    client: StateflowKafkaClient = await StateflowKafkaClient.create(
        stateflow.init(), brokers="localhost:9092"
    )

    user: User = client.send(
        Event(
            "1234",
            FunctionAddress(FunctionType("global", "User", True), None),
            EventType.Request.InitClass,
            {"args": Arguments({"username": "wouter"})},
        ),
        User,
    )
    await user
    print(user, flush=True)


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
    asyncio.get_event_loop().run_forever()
