from typing import Annotated

from authlib.integrations.starlette_client import StarletteOAuth2App
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, APIKeyQuery
from starlette.status import HTTP_403_FORBIDDEN

from app.session import SessionDep

from .api import GitlabToken, oauth
from .settings import GITLAB_OAUTH_DEFAULT_TOKEN, GITLAB_OAUTH_NAME, SESSION_AUTH_KEY

gitlab_token_query = APIKeyQuery(
    name="gitlab_token",
    scheme_name="GitLab Private Token query",
    auto_error=False,
)
gitlab_token_header = APIKeyHeader(
    name="X-Gitlab-Token",
    scheme_name="GitLab Private Token header",
    auto_error=False,
)


def get_oauth() -> StarletteOAuth2App:
    return oauth.create_client(GITLAB_OAUTH_NAME)


async def get_session_auth(session: SessionDep) -> dict:
    return session[SESSION_AUTH_KEY]


async def get_gitlab_token(
    query_param: Annotated[str, Security(gitlab_token_query)],
    header_param: Annotated[str, Security(gitlab_token_header)],
    session_auth: Annotated[dict, Depends(get_session_auth)],
) -> GitlabToken:
    if query_param:
        token = GitlabToken(
            value=query_param,
            query={"gitlab_token": query_param},
            rc_query={"gitlab_token": query_param},
        )
    elif header_param:
        token = GitlabToken(
            value=header_param,
            query={},
            rc_query={"gitlab_token": header_param},
        )
    elif session_token := session_auth.get("access_token"):
        token = GitlabToken(value=session_token, query={}, rc_query={})
    elif GITLAB_OAUTH_DEFAULT_TOKEN:
        token = GitlabToken(
            value=GITLAB_OAUTH_DEFAULT_TOKEN,
            query={},
            rc_query={},
        )
    else:
        token = None

    if token:
        return token
    raise HTTPException(
        status_code=HTTP_403_FORBIDDEN,
        detail="Missing token, either use login, or pass it as header or query",
    )


AuthAppDep = Annotated[StarletteOAuth2App, Depends(get_oauth)]
SessionAuthDep = Annotated[dict, Depends(get_session_auth)]
GitlabTokenDep = Annotated[GitlabToken, Depends(get_gitlab_token)]
