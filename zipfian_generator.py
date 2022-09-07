import random

ZIPF_CONSTANT = 0.99


class ZipfGenerator:
    """
    Adapted from YCSB's ZipfGenerator here:
    https://github.com/brianfrankcooper/YCSB/blob/master/core/src/main/java/site/ycsb/generator/ZipfianGenerator.java
    That's an implementation from "Quickly Generating Billion-Record Synthetic Databases", Jim Gray et al, SIGMOD 1994.
    """

    def __init__(self, items: int = None, mn: int = None, mx: int = None, zipf_const: float = None):

        if items is not None:
            self.__max = items - 1
            self.__min = 0
            self.__items = items
        else:
            self.__max = mx
            self.__min = mn
            self.__items = self.__max - self.__min + 1

        if zipf_const is not None:
            self.__zipf_constant: float = zipf_const
        else:
            self.__zipf_constant: float = ZIPF_CONSTANT

        self.__zeta = self.zeta_static(self.__max - self.__min + 1, self.__zipf_constant)
        self.__base = self.__min
        self.__theta: float = self.__zipf_constant
        zeta2theta = self.zeta(2, self.__theta)
        self.__alpha: float = 1.0 / (1.0 - self.__theta)
        self.__count_for_zeta: int = items
        self.__eta: float = (1 - pow(2.0 / items, 1 - self.__theta)) / (1 - zeta2theta / self.__zeta)
        self.__allow_item_count_decrease: bool = False

    def __next__(self):
        u: float = random.random()
        uz: float = u * self.__zeta
        if uz < 1.0:
            return self.__base
        if uz < 1.0 + pow(0.5, self.__theta):
            return self.__base + 1
        return self.__base + int(self.__items * pow(self.__eta * u - self.__eta + 1, self.__alpha))

    def __iter__(self):
        return self

    def zeta(self, *params):
        if len(params) == 2:
            n, theta_val = params
            self.__count_for_zeta = n
            return self.zeta_static(n, theta_val)
        elif len(params) == 4:
            st, n, theta_val, initial_sum = params
            self.__count_for_zeta = n
            return self.zeta_static(n, theta_val, theta_val, initial_sum)

    def zeta_static(self, *params):
        if len(params) == 2:
            n, theta = params
            st = 0
            initial_sum = 0
            return self.zeta_sum(st, n, theta, initial_sum)
        elif len(params) == 4:
            st, n, theta, initial_sum = params
            return self.zeta_sum(st, n, theta, initial_sum)

    @staticmethod
    def zeta_sum(st, n, theta, initial_sum):
        s = initial_sum
        for i in range(st, n):
            s += 1 / (pow(i + 1, theta))
        return s


if __name__ == "__main__":
    counts = {}
    g = ZipfGenerator(items=10)
    for _ in range(200):
        num = next(g)
        # print(num)
        if num in counts:
            counts[num] += 1
        else:
            counts[num] = 1
    print(dict(sorted(counts.items(), key=lambda item: -item[1])))
