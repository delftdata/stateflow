import pickle
from _continuation import generator

def external_power(input: int, power: int) -> int:
    return input ** power


class Math:
    def __init__(self, number: int):
        self.number = number

    @generator
    def compute(self, cont, another_number: int) -> int:
        # First part of the computation.
        a = self.number + another_number

        print(f"We just computed a: {a}.")

        # Here we break by switching the coroutine,
        # store the current state
        # and wait until we get the answer for b.
        b = cont.switch()

        # We have the result from b and return c.
        c = a + b
        return c
        #return cont


###
## Step 1
###
# Setup instance.
math = Math(1)

# Open coroutine, this won't execute anything (yet)!
math_coroutine = math.compute(1)
# Compute until first yield.

next(math_coroutine)
# >> We just computed a: 2.

###
## Step 2
###
dumped = pickle.dumps(math_coroutine)

