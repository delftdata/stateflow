# Event-Driven Dataflow | Design Document

## Terminology

| __Term__                   | __Explanation__                                                                                                                                                                            |
|----------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Dataflow                   |                                                                                                                                                                                            |
| Abstract Syntax Tree (AST) | An AST is an abstract tree representation of the syntacic structure of source code of a programming language. In this tree, each node denotes a construct which occurs in the source code. |
## Function Splitting
The goal of the __function splitting__ implementation is to transform a function in such a way that no nested function exists within that function.
Instead, the function is split in such a way that function are not _nested_ but _chained_. For example, consider this function:

```python
def sqr(x: int) -> int:
    y = x**2
    return y

def compute(a: int) -> int:
    b = a + 1
    c = sqr(b * 3)
    d = b + c
    return d

compute(3)
```

The `compute` function has a call to another function `sqr`, in a simple dataflow representation that would look like the following. Note: edges represent dataflow and nodes represent computation.
```
--(a=3)--> compute(a=3) --(d)-->
                |      ∧
             (b * 3)   |
                |     (y)
                ∨      |
             sqr(x=b * 3)
```

If we perform __function splitting__ where we get rid of the nested function and turn it into a 'chain of functions', the code would look like this.
```python
def sqr(x: int) -> int:
    y = x**2
    return y

def compute_1(a):
    b = a + 1
    sqr_1 = b * 3
    return a, b, sqr_1

def compute_2(b, sqr_result):
    c = sqr_result
    d = b + c
    return d
```
Now the dataflow is _able_ to look like this:
```
--(a=3)--> compute_1(a = 3) --(a, b, sqr_1)--> sqr(x=sqr_1) --(a, b, sqr_1, y)--> compute_2(b=b, sqr_result=y)--(d)-->
```
Obviously, we need some sort of 'control' or 'runtime' which will ensure that the correct 'chain of functions' is invoked in the correct order with the correct parameters and data is preserved between function calls.

The difficulty of this task is to identify _where_ to split a function, to _isolate_ this function call and add to a function _chain_ in such a way that the semantics of the function chain is equal to that of the function to split.
For the function splitting we consider the abstract syntax tree (AST)
### High Level Algorithm

1. 