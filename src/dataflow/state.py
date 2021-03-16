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
