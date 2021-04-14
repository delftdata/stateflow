from demo_common import User, Item, stateflow
from src.client.kafka_client import StateflowClient, StateflowKafkaClient
from src.client.future import StateflowFuture, StateflowFailure


stateflow.init()

# TODO
# 1. Being able to serialize these flow nodes (encode with uuid).
# 2. Add flags to each flow node PENDING AND DONE
# 3. Have a results per flow node
# 4. Implementation in router and class wrapper.
# 5. E2E


client: StateflowClient = StateflowKafkaClient(
    stateflow.init(), brokers="localhost:9092"
)

print("Creating a user: ")
future_user: StateflowFuture[User] = User("wouter-user")

try:
    user: User = future_user.get()
except StateflowFailure:
    user: User = client.find(User, "wouter-user").get()

print(user.balance.get())

print("Creating an item: ")
future_item: StateflowFuture[Item] = Item("coke", 1)

try:
    item: Item = future_item.get()
except StateflowFailure:
    item: Item = client.find(Item, "coke").get()
item.stock = 1
user.balance = 10


print(user.balance.get())
print(item.stock.get())
print(item.price.get())

print(user.buy_item(100, item).get())

print(user.buy_item(1, item).get())
