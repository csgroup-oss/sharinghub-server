# Copyright 2025, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of SharingHub project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
