import os
from pathlib import Path
from typing import Any, Callable

import yaml


def read_config(file_path: str | os.PathLike, /) -> dict:
    if os.path.isfile(file_path):
        with open(file_path, "r") as f:
            return yaml.load(f, Loader=yaml.SafeLoader)
    return {}


def conf(
    mapping: dict,
    path: str,
    env_var: str = "",
    /,
    *,
    default: Any = None,
    cast: Callable[[Any], Any] | None = None,
) -> Any:
    cursor = mapping
    paths = path.split(".")

    for i, p in enumerate(paths):
        cursor = cursor.get(p)

        if i == len(paths) - 1:
            val = cursor
            if env_var:
                val = os.environ.get(env_var, val)

            if val and cast:
                val = cast(val)

            if val is None:
                val = default

            return val

        elif not cursor or not isinstance(cursor, dict):
            return default


def cbool() -> Callable[[Any], bool]:
    return lambda v: str(v).lower() in ["true", "1"]


def clist(*, sep: str = ",") -> Callable[[str], list[str]]:
    return lambda v: v if isinstance(v, list) else v.split(sep)


def cpath() -> Callable[[str | Path], Path]:
    return lambda v: (Path(v) if not isinstance(v, Path) else v).absolute()
