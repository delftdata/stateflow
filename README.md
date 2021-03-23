# Stateful dataflows
Prototype which extracts stateful dataflows by analysing Python code. 

To visualize a dataflow:
```python
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

    def __hash__(self):
        return self.username

statefun.init()
statefun.visualize()
```

This will run a Flask application, visualizing the dataflow on `localhost:5000`. Make sure to have [Graphviz](https://graphviz.org/) installed on your system.

## Code to Dataflow
In the first phase of this conversion, we analyze the Abstract Syntax Tree of the class definitions. This analysis includes:
1. **State extraction**   
In each `FunctionDef` we look for all attributes associated with `self`. All `self` attributes are extracted and merged, prioritizing typed declarations.
This approach assumes that __all__ state of a class, is assigned (or defined) at least once somewhere in the functions of the classes.
## TODO
- [x] Add class and function dependencies (think about when state is necessary, when functions need to be called, etc.)
- [ ] Move the responsibility of parsing each (sub-)AST to a static method in each 'type' (i.e. PyClass, PyFunction, etc.).
- [ ] Read (state) only functions, write (state) functions. Add this as property in the class.
- [x] Model data flow on the function granularity
- [ ] Support/model state write of input instances (e.g. `item.price = 9`)
- [ ] Propagate if functions in the flow only access state or also write to it (this way we know if we need to lock it!). 
- [ ] Somehow model keys
- [ ] Support `AugAssign` to identify state. 
- [ ] Support stateless functions (i.e. function defs)
- [x] Move parameters from `OrderedDict` datatype to `List[PyParam]`  
- [ ] Add abstraction between dataflow and graphviz
- [ ] Docstrings
- [ ] Test
