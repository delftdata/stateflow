from demo_common import User, Item, stateflow
from src.client.kafka_client import StateflowClient, StateflowKafkaClient
from src.client.future import StateflowFuture, StateflowFailure
import time
from src.serialization.pickle_serializer import PickleSerializer

stateflow.init()

client: StateflowClient = StateflowKafkaClient(
    stateflow.init(), brokers="localhost:9092", serializer=PickleSerializer()
)

client.wait_until_healthy(timeout=10)

print("Creating a user: ")
future_user: StateflowFuture[User] = User("wouter-user")

try:
    user: User = future_user.get()
except StateflowFailure:
    user: User = client.find(User, "wouter-user").get()

print("Done!")
for_loop: int = user.simple_for_loop(user).get()
print(for_loop)
# print("")
# print("Creating an item: ")
# future_item: StateflowFuture[Item] = Item("coke", 10)
#
# try:
#     item: Item = future_item.get()
# except StateflowFailure:
#     item: Item = client.find(Item, "coke").get()
# print("Done!")
# print("")
#
# item.stock = 5
# user.balance = 10
#
#
# start_time = time.time()
# print(f"User balance: {user.balance.get()}")
# print(f"Item stock: {item.stock.get()} and price {item.price.get()}")
#
# print()
# # This is impossible.
# print(f"Let's try to buy 100 coke's of 10EU?: {user.buy_item(100, item).get()}")
#
# # Jeej we buy one, user will end up with 0 balance and there is 4 left in stock.
# print(f"Lets' try to buy 1 coke's of 10EU?: {user.buy_item(1, item).get()}")
#
# print()
# # user balance 0, stock 4.
# print(f"Final user balance: {user.balance.get()}")
# print(f"Final item stock: {item.stock.get()}")
# end_time = time.time()
# diff = (end_time - start_time) * 1000
#
# print(f"\nThat took {diff}ms")
