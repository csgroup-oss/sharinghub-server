from typing import Any


def singleton(cls: type) -> object:
    instances = {}

    def getinstance(*args: Any, **kwargs: Any) -> object:
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return getinstance


def merge(a: dict, b: dict) -> dict:
    keys = list(set(a) | set(b))
    res = {}
    for k in keys:
        if k in a and k in b:
            if isinstance(a[k], dict) and isinstance(b[k], dict):
                res[k] = merge(a[k], b[k])
            else:
                res[k] = b[k]  # b priority
        elif k in a:
            res[k] = a[k]
        else:  # k in b
            res[k] = b[k]
    return res
