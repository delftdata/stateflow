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

    def simple_for_loop(self, user: "User"):
        a = 3
        for x in [1, 2]:
            if x == 1:
                k = 1
                for y in [1, 2]:
                    if y == 1:
                        r = 1 + a
                    else:
                        z = 1

                    print(y)
                print(x)
            else:
                p = 1

        return a, k, r, z, p

    def __key__(self):
        return self.username
