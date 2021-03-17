from .event import Event


class StatefulFun:
    def __init__(self, class_name: str):
        self.class_name = class_name

    def invoke(self, event: Event) -> Event:
        # Get correct function
        # Prepare fun arguments,
        # Setup function with state, without calling _init_.
        # Execute it
        # get output Event
        pass
