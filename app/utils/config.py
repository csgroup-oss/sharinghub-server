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

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.utils import merge


@dataclass
class Config:
    def __init__(
        self,
        mapping: dict,
        files: list[str] | None = None,
        secret_dir: str | None = None,
    ) -> None:
        self.mapping = mapping
        self.files = files if files else []
        self.secret_dir = Path(secret_dir) if secret_dir else Path.cwd()

    @staticmethod
    def load(*files: str, **kwargs: Any) -> "Config":
        mapping: dict = {}
        _files = []
        for file_path in files:
            if os.path.isfile(file_path):
                _files.append(os.path.realpath(file_path))
                with open(file_path) as f:
                    _content = yaml.load(f, Loader=yaml.SafeLoader)
                if isinstance(_content, dict):
                    mapping = merge(mapping, _content)
        return Config(mapping, files=_files, **kwargs)

    def __call__(
        self,
        path: str = "",
        env_var: str = "",
        file_name: str = "",
        *,
        default: Any = None,  # noqa: ANN401
        cast: Callable[[Any], Any] | None = None,
    ) -> Any:  # noqa: ANN401
        val = None
        cursor: Any = self.mapping

        if path:
            paths = path.split(".")
            for i, p in enumerate(paths):
                cursor = cursor.get(p)
                if i == len(paths) - 1:
                    val = cursor
                if cursor is None or not isinstance(cursor, dict):
                    break
        if env_var:
            val = os.environ.get(env_var, val)
        if file_name:
            file_path = self.secret_dir / file_name
            if file_path.is_file():
                with file_path.open() as f:
                    val = f.read().strip()

        if val is None:
            val = default
        if val and cast:
            val = cast(val)
        return val


def cbool() -> Callable[[Any], bool]:
    return lambda v: str(v).lower() in ["true", "1"]


def clist(*, sep: str = ",") -> Callable[[str], list[str]]:
    return lambda v: v if isinstance(v, list) else v.split(sep)


def cpath() -> Callable[[str | Path], Path]:
    return lambda v: (Path(v) if not isinstance(v, Path) else v).absolute()


def cdict(*, sep: str = ",") -> Callable[[str], dict]:
    return lambda v: (
        dict(e.split(":", 1) for e in v.split(sep)) if isinstance(v, str) else v
    )


def cjson() -> Callable[[str], dict | list | None]:
    return lambda v: json.loads(v) if isinstance(v, str) else v
