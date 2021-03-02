Let's assume the following example code:
```python
@dataflow
def sqrt(a: int) -> int:
        return a**2
    
@dataflow
class Fun:
    
    def __init__(self, id: int):
        self.id = id

    def compute(self, a: int) -> int:
        c = a * self.id
        d = sqrt(c)
        e = d + self.id
        return e
```

If we want to execute Fun(1).compute(3), we need to split the function compute in such a way that:
1) First we compute c, and then return with calling sqrt(c)
2) After sqrt(c) is computed, we compute e and return.

A good first step (we consider only a single split):
1) Identifying where the call is in the AST hierarchy.
2) See how we can 'split'