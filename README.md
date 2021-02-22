# Stateful dataflows
Prototype which extracts stateful dataflows by analysing Python code. 

To visualize a dataflow:
```python
import statefun
from statefun import dataflow


@dataflow
class Item:
    def __init__(self, price: int):
        self.price: int = price
        self.stock: int = 0

    def update_stock(self, delta_stock: int) -> bool:
        if (self.stock + delta_stock) < 0:
            return False  # We can't have a negative stock.

        self.stock += delta_stock


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

    def get_balance(self) -> int:
        return self.balance


statefun.init()
statefun.visualize()
```

This will run a Flask application, visualizing the dataflow on `localhost:5000`.

## TODO
- [ ] Add class and function dependencies (think about when state is necessary, when functions need to be called, etc.)
- [ ] Read (state) only functions, make write functions
- [ ] Model data flow on the function granularity
- [ ] Add abstraction between dataflow and graphviz
- [ ] Docstrings
- [ ] Test