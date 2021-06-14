from demo_common import User, Item, stateflow
from src.client.kafka_client import StateflowClient, StateflowKafkaClient
from src.client.aws_client import AWSKinesisClient
from src.client.future import StateflowFuture, StateflowFailure
import time
from src.serialization.pickle_serializer import PickleSerializer

# stateflow.init()

# client: StateflowClient = StateflowKafkaClient(
#     stateflow.init(), brokers="localhost:9092", serializer=PickleSerializer()
# )
client: StateflowClient = AWSKinesisClient(stateflow.init())
# client.wait_until_healthy(timeout=10)

print("Creating a user: ")
future_user: StateflowFuture[User] = User("wouter-user")

try:
    user: User = future_user.get()
except StateflowFailure:
    user: User = client.find(User, "wouter-user").get()

future_user2: StateflowFuture[User] = User("wouter-user2")

try:
    user2: User = future_user2.get()
except StateflowFailure:
    user2: User = client.find(User, "wouter-user2").get()


print("Done!")
for_loop: int = user.simple_for_loop([user, user2]).get(timeout=5)
print(user.balance.get())
print(user2.balance.get())
# print(for_loop)
# print("")
print("Creating an item: ")
future_item: StateflowFuture[Item] = Item("coke", 10)

try:
    item: Item = future_item.get()
except StateflowFailure:
    item: Item = client.find(Item, "coke").get()
print("Done creating coke!")
print("")


future_item2: StateflowFuture[Item] = Item("pepsi", 10)

try:
    item2: Item = future_item2.get()
except StateflowFailure:
    item2: Item = client.find(Item, "pepsi").get()
print("Created both items!")
print("")

hi = user.state_requests([item, item2]).get(timeout=10)
print(hi)
item.stock = 5
user.balance = 10


start_time = time.time()
print(f"User balance: {user.balance.get()}")
print(f"Item stock: {item.stock.get()} and price {item.price.get()}")

print()
# This is impossible.
print(f"Let's try to buy 100 coke's of 10EU?: {user.buy_item(100, item).get()}")

# Jeej we buy one, user will end up with 0 balance and there is 4 left in stock.
print(f"Lets' try to buy 1 coke's of 10EU?: {user.buy_item(1, item).get()}")

print()
# user balance 0, stock 4.
print(f"Final user balance: {user.balance.get()}")
print(f"Final item stock: {item.stock.get()}")
end_time = time.time()
diff = (end_time - start_time) * 1000

print(f"\nThat took {diff}ms")
