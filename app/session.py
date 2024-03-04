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
