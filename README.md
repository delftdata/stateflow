# StateFlow
[![CI](https://github.com/wzorgdrager/stateful_dataflows/actions/workflows/python-app.yml/badge.svg)](https://github.com/wzorgdrager/stateful_dataflows/actions/workflows/python-app.yml)
[![codecov](https://codecov.io/gh/wzorgdrager/stateful_dataflows/branch/main/graph/badge.svg)](https://codecov.io/gh/wzorgdrager/stateful_dataflows)

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

## Stateflow vs Actors
...
## Phase 1: Code Analysis
In the first phase of this conversion, we analyze the AST of the class definitions and extract all necessary information to initialize a dataflow. For this code analysis, we consider **classes**, **(stateless) functions** and **lambda's**.
### Classes
Classes will eventually be turned into stateful functions. The following information will be extracted and stored in a `ClassDescriptor`:
1. **State extraction**   
In each `FunctionDef` we look for all attributes associated with `self`. All `self` attributes are extracted and merged, prioritizing typed declarations.
This approach assumes that __all__ state of a class, is assigned (or defined) at least once somewhere in the functions of the classes.
2. **Method extraction**   
In each `ClassDef`, we look for all the `FunctionDef` which will be analyzed and result in a `MethodDescriptor`. 
For each method we extract:
    - Method input: The parameters of a function are stored in a `InputDescriptor`. 
         - For method parameters we do not allow _default_ values nor `*args` and `**kwargs`.
         - If a parameter has a call or attribute access, we need the type of the parameter to be defined.
    - Method output: The output of a function is stored in a `OutputDescriptor`. Since a method can have multiple 'return paths', the OutputDescriptor holds a list of potential returns. We don't care about the variable names that are returned, so we only store the _amount_ of return variables and potentially the types. 
         - If a return annotation is given, each return statement needs to match this annotation in terms of length.
         - No function calls are allowed in a return statement. 
    - Read-only: we extract if a function is read or write (to state). I.e. assignments to `self` is done. 

Lastly, we have some _restrictions_ for a class:
- Functions cannot be `async`. It does not make sense in the context of StateFlow where functions are already running completely asynchronous.
- There can't be functions with the same name. Similar to Python behaviour, we just pick the latest function declaration.
- The `__init__` method is a special method that always needs to be declared and we do not allow any function calls there OR parameters of other functions.
- A class has to define a `__hash__` function to decide on the `key` of the stateful functions. **TODO**: what are the restrictions of this hash func.

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
