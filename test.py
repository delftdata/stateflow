def forx(l):
    try:
        x = next(l)
    except StopIteration:
        return {"_type": StopIteration}
    return x, l


ll = range(0, 3)

x, l = forx(iter(ll))
print(x)


x, l = forx(l)
print(x)

x, l = forx(l)
print(x)

x = forx(l)
print(x)
