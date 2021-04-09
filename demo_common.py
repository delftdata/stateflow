import src.stateflow as stateflow


@stateflow.stateflow
class User:
    def __init__(self, username: str):
        self.username: str = username
        self.balance: int = 0

    def update_balance(self, x: int):
        self.balance += x

    def __key__(self):
        return self.username
