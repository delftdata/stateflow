import stateflow


@stateflow.stateflow
class YCSBEntity:

    def __init__(self, key: str, value: int):
        # insert
        self.key: str = key
        self.value: int = value

    def read(self):
        return self.key, self.value

    def update(self, new_value: int):
        self.value = new_value

    def add_funds(self, transfer_amount: int):
        self.value += transfer_amount

    def transfer(self, transfer_amount: int, other_entity: "YCSBEntity") -> bool:
        new_value: int = self.value - transfer_amount
        if new_value < 0:
            return False
        self.value = new_value
        other_entity.add_funds(transfer_amount)
        return True

    def __key__(self):
        return self.key
