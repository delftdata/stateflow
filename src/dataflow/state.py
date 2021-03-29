from typing import Dict, Any, List
import ujson


class State:
    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, item):
        return self._data[item]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __str__(self):
        return str(self._data)

    def get_keys(self):
        return self._data.keys()

    def get(self):
        return self._data

    @staticmethod
    def serialize(state: "State") -> str:
        return ujson.encode(state)

    @staticmethod
    def deserialize(state_serialized: str) -> "State":
        return ujson.decode(state_serialized)


class StateDescriptor:
    def __init__(self, state_desc: Dict[str, Any]):
        self._state_desc = state_desc

    def get_keys(self):
        return self._state_desc.keys()

    def match(self, state: State) -> State:
        return self.get_keys() == state.get_keys()

    def __str__(self):
        return str(list(self._state_desc.keys()))

    def __contains__(self, item):
        return item in self._state_desc

    def __getitem__(self, item):
        return self._state_desc[item]

    def __setitem__(self, key, value):
        self._state_desc[key] = value
