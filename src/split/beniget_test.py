import beniget
import gast as ast
from example import *
import inspect
import textwrap

code = "from math import cos, sin; print(cos(3))"
calculator = Calculator(1)
module = ast.parse(textwrap.dedent(inspect.getsource(calculator.computation.__code__)))
duc = beniget.DefUseChains()
duc.visit(module)

for key, value in duc.locals.items():
    print(f"k {key}, v {value}")
