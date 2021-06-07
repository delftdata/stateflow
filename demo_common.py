import uuid
from typing import List
import src.stateflow as stateflow


@stateflow.stateflow
class Item:
    def __init__(self, item_name: str, price: int):
        self.item_name: str = item_name
        self.stock: int = 0
        self.price: int = price

    def update_stock(self, amount: int) -> bool:
        if (self.stock + amount) < 0:  # We can't get a stock < 0.
            return False

        self.stock += amount
        return True

    def __key__(self):
        return self.item_name


@stateflow.stateflow
class User:
    def __init__(self, username: str):
        self.username: str = username
        self.balance: int = 1
        self.items: List[Item] = []

    def update_balance(self, x: int):
        self.balance += x

    def get_balance(self):
        return self.balance

    def buy_item(self, amount: int, item: Item) -> bool:
        total_price = amount * item.price

        if self.balance < total_price:
            return False

        # Decrease the stock.
        decrease_stock = item.update_stock(-amount)

        if not decrease_stock:
            return False  # For some reason, stock couldn't be decreased.

        self.balance -= total_price
        return True

    def simple_for_loop(self, users: List["User"]):
        i = 0
        for user in users:
            if i > 0:
                user.update_balance(9)
            else:
                user.update_balance(4)
            i += 1

    def __key__(self):
        return self.username
