from demo_common import User, stateflow
from src.client.kafka_client import StateflowClient, StateflowKafkaClient
from src.client.future import StateflowFuture


client: StateflowClient = StateflowKafkaClient(
    stateflow.init(), brokers="localhost:9092"
)

print("Creating a user: ")

future_user: StateflowFuture[User] = User("wouter-user")
user: User = future_user.get()
print(user.balance.get())
