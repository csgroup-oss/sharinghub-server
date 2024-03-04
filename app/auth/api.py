from typing import Any, NamedTuple

from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App
from fastapi import HTTPException
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from app.settings import GITLAB_URL

from .settings import GITLAB_OAUTH

_oauth = OAuth()
_OAUTH_NAME = "gitlab"
_MANDATORY_KEYS = ["client_id", "client_secret", "server_metadata_url"]


class GitlabToken(NamedTuple):
    value: str
    query: dict[str, Any]
    rc_query: dict[str, Any]


async def get_oauth() -> StarletteOAuth2App | None:
    if oauth_client := _oauth.create_client(_OAUTH_NAME):
        return oauth_client
    openid_url = f"{GITLAB_URL.removesuffix('/')}/.well-known/openid-configuration"
    oauth_conf = {"server_metadata_url": openid_url, **GITLAB_OAUTH}
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
