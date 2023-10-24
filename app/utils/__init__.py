def singleton(cls):
    instances = {}

    def getinstance(*args, **kwargs):
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
