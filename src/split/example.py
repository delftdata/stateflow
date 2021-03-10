import math


def sqr(x: int) -> int:
    y = x ** 2
    return y


class Calculator:
    def __init__(self, x: int):
        self.x = x

    def computation(self, y):
        a = self.x + 1
        sqr(y + 2)
        sqr(y + 3)
        c = a + self.x
        return c
