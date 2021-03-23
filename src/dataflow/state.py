from typing import Dict, Any


class State:
    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, item):
        return self._data[item]

    def __setitem__(self, key, value):
        self._data[key] = value

    @staticmethod
    def serialize(state: "State") -> str:
        pass

    @staticmethod
    def deserialize(state_serialized: str) -> "State":
        pass


class StateDescription:
    def __init__(self, state_desc: Dict[str, Any]):
        self._state_desc = state_desc

    def __contains__(self, item):
        return item in self._state_desc

    def __getitem__(self, item):
        return self._state_desc[item]

    def __setitem__(self, key, value):
        self._state_desc[key] = value
