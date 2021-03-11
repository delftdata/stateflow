import math


def sqr(x: int) -> int:
    y = x ** 2
    return y


class Calculator:
    def __init__(self, x: int):
        self.x = x

    def computation(self, y):
        a = self.x + 1
        b = sqr(y + 2) + sqr(y + 3)
        c = a + self.x + b
        return c

    def fun_0(self, y):
        a = self.x + 1
        sqr_0_arg_0 = y + 2
        return a, sqr_0_arg_0

    def fun_1(self, y):
        sqr_1_arg_0 = y + 3
        return sqr_1_arg_0

    def fun_2(self, a, sqr_0_result, sqr_1_result):
        b = sqr_0_result + sqr_1_result
        c = a + self.x + b
        return c
