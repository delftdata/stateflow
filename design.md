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
