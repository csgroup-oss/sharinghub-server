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

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request

from app.auth.settings import SESSION_AUTH_KEY


async def get_session(request: Request) -> dict:
    request.session.setdefault(SESSION_AUTH_KEY, {})
    return request.session


def _clean_session(session: dict) -> None:
    # Clean authlib states if still exists
    for key in list(session.keys()):
        if key.startswith("_state"):
            del session[key]


async def post_clean_session(request: Request) -> AsyncGenerator[None, None]:
    try:
        yield
    finally:
        _clean_session(request.session)


async def pre_clean_session(request: Request) -> AsyncGenerator[None, None]:
    _clean_session(request.session)
    yield


SessionDep = Annotated[dict, Depends(get_session)]
PreCleanSessionDep = Depends(pre_clean_session)
PostCleanSessionDep = Depends(post_clean_session)
