import asyncio
import datetime
import time

from universalis.common.stateflow_ingress import IngressTypes
from universalis.universalis import Universalis
import demo_common
from demo_common import User, Item, stateflow
from stateflow.client.future import StateflowFuture, StateflowFailure
from stateflow.client.universalis_client import UniversalisClient
from stateflow.runtime.universalis.universalis_runtime import UniversalisRuntime


UNIVERSALIS_HOST: str = 'localhost'
UNIVERSALIS_PORT: int = 8886
KAFKA_URL = 'localhost:9093'


async def main():
    # Initialize stateflow
    flow = stateflow.init()

    universalis_interface = Universalis(UNIVERSALIS_HOST, UNIVERSALIS_PORT,
                                        ingress_type=IngressTypes.KAFKA,
                                        kafka_url=KAFKA_URL)

    runtime: UniversalisRuntime = UniversalisRuntime(flow,
                                                     universalis_interface,
                                                     "Stateflow",
                                                     n_partitions=6)

    universalis_operators = await runtime.run((demo_common, ))

    print(universalis_operators.keys())

    flow = stateflow.init()
    client: UniversalisClient = UniversalisClient(flow=flow,
                                                  universalis_client=universalis_interface,
                                                  kafka_url=KAFKA_URL,
                                                  operators=universalis_operators)

    client.wait_until_healthy(timeout=1)

    print("Creating a user: ")
    start = datetime.datetime.now()
    future_user: StateflowFuture[User] = User("wouter-user")

    try:
        user: User = future_user.get()
    except StateflowFailure:
        user: User = client.find(User, "wouter-user").get()

    end = datetime.datetime.now()
    delta = end - start
    print(f"Creating user took {delta.total_seconds() * 1000}ms")

    print("Creating another user")
    start = datetime.datetime.now()
    future_user2: StateflowFuture[User] = User("wouter-user2")

    try:
        user2: User = future_user2.get()
    except StateflowFailure:
        user2: User = client.find(User, "wouter-user2").get()
    end = datetime.datetime.now()
    delta = end - start
    print(f"Creating another user took {delta.total_seconds() * 1000}ms")

    print("Done!")

    start = datetime.datetime.now()
    print('Running for loop')
    for_loop: int = user.simple_for_loop([user, user2]).get()
    print(f'For loop result: {for_loop}')
    end = datetime.datetime.now()
    delta = end - start
    print(f"Simple for loop took {delta.total_seconds() * 1000}ms")

    if user.balance.get() != 5:
        print(f"\nThis should have been 5 but it is: {user.balance.get()}\n")
        exit()

    if user2.balance.get() != 10:
        print(f"\nThis should have been 10 but it is: {user2.balance.get()}\n")
        exit()

    print("Creating an item: ")
    start = datetime.datetime.now()
    future_item: StateflowFuture[Item] = Item("coke", 10)

    try:
        item: Item = future_item.get()
    except StateflowFailure:
        item: Item = client.find(Item, "coke").get()
    end = datetime.datetime.now()
    delta = end - start
    print(f"Creating coke took {delta.total_seconds() * 1000}ms")

    start = datetime.datetime.now()
    future_item2: StateflowFuture[Item] = Item("pepsi", 10)

    try:
        item2: Item = future_item2.get()
    except StateflowFailure:
        item2: Item = client.find(Item, "pepsi").get()
    end = datetime.datetime.now()
    delta = end - start
    print(f"Creating another pepsi took {delta.total_seconds() * 1000}ms")
    print(item.item_name.get())
    print(item2.item_name.get())

    print('-------------------------------------------------')
    print('Starting complex logic')
    print('-------------------------------------------------')
    start = datetime.datetime.now()
    hi = user.state_requests([item, item2]).get(timeout=10)
    print(hi)
    end = datetime.datetime.now()
    delta = end - start
    print(f"State requests took {delta.total_seconds() * 1000}ms")
    item.stock = 5
    user.balance = 10

    start_time = time.time()
    print(f"User balance: {user.balance.get()}")
    print(f"Item stock: {item.stock.get()} and price {item.price.get()}")

    print()
    # This is impossible.
    start = datetime.datetime.now()
    print(f"Let's try to buy 100 coke's of 10EU?: {user.buy_item(100, item).get()}")
    end = datetime.datetime.now()
    delta = end - start
    print(f"Buy item took {delta.total_seconds() * 1000}ms")

    # Jeej we buy one, user will end up with 0 balance and there is 4 left in stock.
    start = datetime.datetime.now()
    print(f"Lets' try to buy 1 coke's of 10EU?: {user.buy_item(1, item).get()}")
    end = datetime.datetime.now()
    delta = end - start
    print(f"Another buy item took {delta.total_seconds() * 1000}ms")

    print()
    # user balance 0, stock 4.
    print(f"Final user balance: {user.balance.get()}")
    print(f"Final item stock: {item.stock.get()}")
    end_time = time.time()
    diff = (end_time - start_time) * 1000

    print(f"\nThat took {diff}ms")


asyncio.run(main())
