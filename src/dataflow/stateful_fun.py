from .event import Event
from .state import StateDescription, NoType
from typing import Any


class StatefulFun:
    def __init__(self, class_name: str, state_desc: StateDescription):
        self.class_name = class_name
        self.state_desc = state_desc

    def has_state(self, key: str) -> bool:
        return key in self.state_desc

    def get_state_type(self, key: str) -> Any:
        if not self.has_state(key):
            raise AttributeError(
                f"{self.class_name} does not have any state with name {key}."
            )

        return self.state_desc[key]

    def invoke(self, event: Event) -> Event:
        # Get correct function
        # Prepare fun arguments,
        # Setup function with state, without calling _init_.
        # Execute it
        # get output Event
        pass
