from demo_common import User, Item, stateflow
from src.client.kafka_client import StateflowClient, StateflowKafkaClient
from src.client.future import StateflowFuture, StateflowFailure


stateflow.init()


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
future_item: StateflowFuture[Item] = Item("coke", 5)

try:
    item: Item = future_item.get()
except StateflowFailure:
    item: Item = client.find(Item, "coke").get()

print(item.price.get())
