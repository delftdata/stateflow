import statefun
from statefun import dataflow


@dataflow
class Item:
    def __init__(self, item_id: str, price: int):
        self.item_id: str = item_id
        self.price: int = price
        self.stock: int = 0

    def update_stock(self, delta_stock: int) -> bool:
        if (self.stock + delta_stock) < 0:
            return False  # We can't have a negative stock.

        self.stock += delta_stock
        return True

    def __hash__(self):
        return self.item_id


@dataflow
class UserAccount:
    def __init__(self, username: str):
        self.username: int = username
        self.balance: int = 0

    # Item state could be available already.
    def buy_item(self, item: Item, amount: int) -> bool:
        if amount * item.price > self.balance:
            return False  # Not enough balance

        # Decrease balance if amount is properly subtracted from stock.
        if item.update_stock(-amount):
            self.balance -= amount * item.price

        return True

    def get_balance(self) -> int:
        return self.balance

    # def get_balance_2(self, item: Item) -> int:
    #     balance_diff: int = item.price
    #     return self.balance - balance_diff

    def __hash__(self):
        return self.username


statefun.init()
statefun.visualize()
