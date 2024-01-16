from collections import namedtuple
from collections.abc import AsyncGenerator
from typing import Annotated

from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App
from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader, APIKeyQuery
from starlette.status import HTTP_403_FORBIDDEN, HTTP_500_INTERNAL_SERVER_ERROR

from app.config import (
    GITLAB_OAUTH,
    GITLAB_OAUTH_DEFAULT_TOKEN,
    GITLAB_URL,
    SESSION_AUTH_KEY,
)

gitlab_token_query = APIKeyQuery(
    name="gitlab_token", scheme_name="GitLab Private Token query", auto_error=False
)
gitlab_token_header = APIKeyHeader(
    name="X-Gitlab-Token", scheme_name="GitLab Private Token header", auto_error=False
)
GitlabToken = namedtuple("GitlabToken", ["value", "query", "rc_query"])

_oauth = OAuth()
_OAUTH_NAME = "gitlab"
_MANDATORY_KEYS = ["client_id", "client_secret", "server_metadata_url"]


async def get_oauth() -> StarletteOAuth2App | None:
    if oauth_client := _oauth.create_client(_OAUTH_NAME):
        return oauth_client
    oauth_conf = {
        "server_metadata_url": f"{GITLAB_URL.removesuffix('/')}/.well-known/openid-configuration",
        **GITLAB_OAUTH,
    }
    if all(k in oauth_conf for k in _MANDATORY_KEYS):
        return _oauth.register(
            name=_OAUTH_NAME,
            client_kwargs={
                "scope": "openid email read_user profile api",
                "timeout": 10.0,
            },
            **oauth_conf,
        )
    raise HTTPException(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        detail="GitLab authentication not configured",
    )


async def get_session(request: Request) -> dict:
    request.session.setdefault(SESSION_AUTH_KEY, {})
    return request.session


async def get_session_auth(session: Annotated[dict, Depends(get_session)]) -> dict:
    return session[SESSION_AUTH_KEY]


def _clean_session(session: dict):
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


async def get_gitlab_token(
    query_param: Annotated[str, Security(gitlab_token_query)],
    header_param: Annotated[str, Security(gitlab_token_header)],
    session_auth: Annotated[dict, Depends(get_session_auth)],
) -> GitlabToken:
    if query_param:
        return GitlabToken(
            value=query_param,
            query=dict(gitlab_token=query_param),
            rc_query=dict(gitlab_token=query_param),
        )
    elif header_param:
        return GitlabToken(
            value=header_param, query=dict(), rc_query=dict(gitlab_token=header_param)
        )
    elif session_token := session_auth.get("access_token"):
        return GitlabToken(value=session_token, query=dict(), rc_query=dict())
    elif GITLAB_OAUTH_DEFAULT_TOKEN:
        return GitlabToken(
            value=GITLAB_OAUTH_DEFAULT_TOKEN, query=dict(), rc_query=dict()
        )
    else:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Missing token, either use login, or pass it as header or query",
        )


OAuthDep = Annotated[StarletteOAuth2App, Depends(get_oauth)]
SessionDep = Annotated[dict, Depends(get_session)]
SessionAuthDep = Annotated[dict, Depends(get_session_auth)]
GitlabTokenDep = Annotated[GitlabToken, Depends(get_gitlab_token)]
PreCleanSessionDep = Depends(pre_clean_session)
PostCleanSessionDep = Depends(post_clean_session)
