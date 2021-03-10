# Event-Driven Dataflow | Design Document

## Terminology

| __Term__                   | __Explanation__                                                                                                                                                                            |
|----------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Dataflow                   |                                                                                                                                                                                            |
| Dataflow operator          | h                                                                                                                                                                                          |         
| Dataflow edge | Represent the (direct) data dependencies between dataflow operators. This includes the state of a function. Data flows over the edges and invoke other functions in the form of events. |
| Stateful function | A set of dataflow operators which share the same state.  |
| Stateless function | A single dataflow operator which does _not_ rely on any state and only requires the function (i.e. operator) input.|
| Ingress | An input source which publishes events _into_ the dataflow. |
| Egress | An output source which consumes events _from_ the dataflow. |
| Abstract Syntax Tree (AST) | An AST is an abstract tree representation of the syntacic structure of source code of a programming language. In this tree, each node denotes a construct which occurs in the source code. |
## Function Splitting
The goal of the __function splitting__ implementation is to transform a function in such a way that no nested function exists within that function.
Instead, the function is split in such a way that function are not _nested_ but _chained_. For example, consider this function:

```python
def sqr(x: int) -> int:
    y = x**2
    return y
__
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
This algorithm is applied on the _body_ of a function: In Python this is a list of `ast.stmt` objects.
1. For each `stmt` in the function `body`.
    1. Parse the `stmt`:
        - check if it has a **call** to an external (stateful) function. If it has an call, then store all parameters for this call.
        - find all **definitions** of this statement (i.e. assignments `a = 3`)
        - find all **usages** of this statement (i.e. binary operation `a + 3`)
    2. If the current `stmt` contains a call:
        - 'Split' the function by adding all previous statements to a statement block. The `stmt` with the actual call belongs the _next_ statement block.
        - All parameters for the function call are _added_ as definitions in the previous statement block. For example:
           ```python
            def fun():
               a = 3
               external_call(a + 1)
              ...
           ```
            Will be split like this:
            ```python
               # Statement Block 0
               a = 3
               external_call_0 = a + 1
               # --- SPLIT
               # Statement Block 1
               external_call(external_call_0)
              ...
           ```
          This means that the actual parameter evaluations are done in the previous statement block. Moreover, the 'usages' of the value of the `Assign` are identified.
2. For each statement block:
    1. We will do the actual external function calls **between** statements block. Therefore we add the call result as parameter in the statement block with the call. Moreover the actual call in the statement blocks is replaced with a simple lookup.  
    2. Turn each StatementBlock into a **separate** function. Each function gets renamed as `funcname_pos` (i.e. `compute_0`, `compute_1`, etc.). We consider three scenarios for the function definitions:
        1. The _first_ statement block: this block overrides the body of the original function definition. **TODO: Override return annotation, if it's there**.
        2. The _last_ statement block: this block uses the _original_ return node(s) and no (internal) definitions are returned.
        3. All other statement blocks: this block converts into a function definition where the formal parameters are equal to the usages in that block and the return arguments are the definitions in that block.
        
         
        

### Overriding usages
To decide on the parameters of a (sub-)function, we look at all the usages of that function. More specifically, we look at all the `Name(id, ast.Load())` nodes.
However, a used parameter can also be defined in the same (sub-)function therefore we _remove_ all usages of a statement which are defined before.
For example:
```python
def computation_1(self, b, sqr_result):
    c = sqr_result
    d = b + c
    return d
```
`c` is loaded in the second statement `d = b + c` but has previously been defined. 


### Special cases
- Multiple calls in one statement
- Nested function call
- For loops
- If statements
- While loop
- Operator overloading

# Remarks
- When making the dataflow we consider all potential computations. However, when actually invoking we only consider a part of the dataflow.
For example, an operator may have multiple outputs in the full dataflow graph but for a function invocation it might only need one output.
Maybe call this the 'materialized dataflow'. Come up with example and discuss with Kyriakos.
- Potential PL resources: https://papl.cs.brown.edu/2014/safety-soundness.html and  
https://dl.acm.org/doi/pdf/10.1145/2544173.2509536