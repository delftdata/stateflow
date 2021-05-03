## Stateflow DSL restrictions

You **cannot**:
- Return with a method call to another stateful function. `return item.invoke_another_method()`