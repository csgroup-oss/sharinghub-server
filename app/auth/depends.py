from typing import Annotated

from authlib.integrations.starlette_client import StarletteOAuth2App
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, APIKeyQuery
from starlette.status import HTTP_403_FORBIDDEN

from app.session import SessionDep

from .api import GitlabToken, get_oauth
from .settings import GITLAB_OAUTH_DEFAULT_TOKEN, SESSION_AUTH_KEY

gitlab_token_query = APIKeyQuery(
    name="gitlab_token", scheme_name="GitLab Private Token query", auto_error=False
)
gitlab_token_header = APIKeyHeader(
    name="X-Gitlab-Token", scheme_name="GitLab Private Token header", auto_error=False
)


async def get_session_auth(session: SessionDep) -> dict:
    return session[SESSION_AUTH_KEY]


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
SessionAuthDep = Annotated[dict, Depends(get_session_auth)]
GitlabTokenDep = Annotated[GitlabToken, Depends(get_gitlab_token)]
