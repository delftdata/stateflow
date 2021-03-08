import math


def sqrt(x: int) -> int:
    return math.sqrt(x)


class Calculator:
    def __init__(self, x: int):
        self.x = x

    def computation(self, y: int):
        a = d = self.x + y
        q = y
        c = 3
        b = sqrt(a)
        c = a + b + d
        return c
