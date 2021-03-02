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
        return e() + 1
```

If we want to execute Fun(1).compute(3), we need to split the function compute in such a way that:
1) First we compute c, and then return with calling sqrt(c)
2) After sqrt(c) is computed, we compute e and return.

A good first step (we consider only a single split):
1) Identifying where the call is in the AST hierarchy.
2) See how we can 'split'

A call is just an expression, so it can be evaluated almost _everywhere_. 
We could compute up and until the point where the Call() is done, then set the result of the Call()
and start evaluating the next statements. 