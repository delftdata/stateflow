import math


def sqr(x: int) -> int:
    y = x ** 2
    return y


class Calculator:
    def __init__(self, x: int):
        self.x = x

    def computation(self, a: int) -> int:
        b = a + self.x + 1
        sqr(b * 3)
        y = sqr(b * 2)
        d = y + b
        return d
