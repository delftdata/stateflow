import stateflow
from src.example.shop import User
from src.dataflow.state import State
from src.dataflow.args import Arguments
from src.wrappers.class_wrapper import FailedInvocation, ClassWrapper


@stateflow.stateflow
class Fun:
    def __init__(self, username: str):
        self.x = 3
        self.username = username

    def update_x(self, delta_x: int) -> int:
        self.x -= delta_x
        return self.x

    def __key__(self):
        return self.username


wrapper = stateflow.registered_class[0]


# Create the class
result = wrapper.init_class(Arguments({"username": "wouter"}))

print(
    f"Created class with key: {result.return_results} and state {result.updated_state}."
)
print()

# Throws exception
print(wrapper.invoke("LOL", None, None))
print()
# Invoke delta x
state = result.updated_state
args = Arguments({"delta_x": 5})
result = wrapper.invoke("update_x", state, args)

print(
    f"Invoked method update_x. \n Updated state {result.updated_state}. \n Result: {result.return_results}"
)
