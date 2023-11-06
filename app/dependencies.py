from collections import namedtuple
from typing import Annotated

from authlib.integrations.starlette_client import StarletteOAuth2App
from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader, APIKeyQuery
from starlette.status import HTTP_403_FORBIDDEN, HTTP_500_INTERNAL_SERVER_ERROR

from app.api.auth import get_oauth_config
from app.config import REMOTES, SESSION_AUTH_KEY
from app.utils.http import slugify, url_domain

gitlab_token_query = APIKeyQuery(
    name="gitlab_token", scheme_name="GitLab Private Token query", auto_error=False
)
gitlab_token_header = APIKeyHeader(
    name="X-Gitlab-Token", scheme_name="GitLab Private Token header", auto_error=False
)
GitlabToken = namedtuple("GitlabToken", ["value", "query"])


async def get_oauth(gitlab: str) -> StarletteOAuth2App | None:
    for remote_name, remote_config in REMOTES.items():
        url: str = remote_config.get("url", "")
        if url_domain(url) == gitlab and (oauth := get_oauth_config(remote_name)):
            return oauth
    raise HTTPException(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"GitLab authentication not configured for: {gitlab}",
    )


async def get_session(request: Request) -> dict:
    request.session.setdefault(SESSION_AUTH_KEY, {})
    return request.session


async def get_session_auth(
    session: Annotated[dict, Depends(get_session)], gitlab: str
) -> dict:
    session[SESSION_AUTH_KEY].setdefault(gitlab, {})
    return session[SESSION_AUTH_KEY][gitlab]


async def get_session_auth_token(
    session_auth: Annotated[dict, Depends(get_session_auth)]
) -> str | None:
    return session_auth.get("token", {}).get("access_token")


async def get_gitlab_token(
    query_param: Annotated[str, Security(gitlab_token_query)],
    header_param: Annotated[str, Security(gitlab_token_header)],
    session_token: Annotated[str | None, Depends(get_session_auth_token)],
) -> GitlabToken:
    if query_param:
        return GitlabToken(value=query_param, query=dict(gitlab_token=query_param))
    elif header_param:
        return GitlabToken(value=header_param, query=dict())
    elif session_token:
        return GitlabToken(value=session_token, query=dict())
    else:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Missing token, either use login, or pass it as header or query",
        )


async def get_gitlab_config(gitlab: str) -> dict:
    for remote_name, remote_config in REMOTES.items():
        url: str = remote_config.get("url", "")
        if url_domain(url) == gitlab:
            return {
                **remote_config,
                "name": remote_name,
                "url": url.removesuffix("/"),
                "path": gitlab,
            }
    return {
        "name": slugify(gitlab).replace("-", ""),
        "url": f"https://{gitlab}",
        "path": gitlab,
    }


OAuthDep = Annotated[StarletteOAuth2App, Depends(get_oauth)]
SessionDep = Annotated[dict, Depends(get_session)]
SessionAuthDep = Annotated[dict, Depends(get_session_auth)]
GitlabTokenDep = Annotated[GitlabToken, Depends(get_gitlab_token)]
GitlabConfigDep = Annotated[dict, Depends(get_gitlab_config)]
