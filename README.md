# StateFlow
[![CI](https://github.com/wzorgdrager/stateful_dataflows/actions/workflows/python-app.yml/badge.svg)](https://github.com/wzorgdrager/stateful_dataflows/actions/workflows/python-app.yml)
[![codecov](https://codecov.io/gh/wzorgdrager/stateful_dataflows/branch/main/graph/badge.svg)](https://codecov.io/gh/wzorgdrager/stateful_dataflows)

Prototype which extracts stateful dataflows by analysing Python code. 

To visualize a dataflow:
```python
from typing import List

@stateflow
class Item:
    def __init__(self, item_id: int, name: str, price: int):
        self.item_id: int = item_id
        self.name: str = name
        self.price = price
        self.stock: int = 0

    def update_stock(self, delta_stock: int) -> bool:
        if self.stock + delta_stock < 0:
            return False

        self.stock += delta_stock
        return True

    def __key__(self):
        return self.item_id

@stateflow
class User:
    def __init__(self, username: str):
        self.username: str = username
        self.balance: int = 0
        self.items: List[Item] = []

    def update_balance(self, balance: int):
        if self.balance + balance < 0:
            return False

        self.balance += balance
        return True, True

    def buy_item(self, item: Item, amount: int) -> bool:
        price = item.price * amount
        if self.balance - price < 0:
            return False

        is_updated: bool = item.update_stock(amount)

        if is_updated:
            self.balance -= price
            return True

    def __key__(self):
        return self.username

stateflow.init()
```