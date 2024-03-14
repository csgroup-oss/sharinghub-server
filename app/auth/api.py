from typing import Any, NamedTuple

from authlib.integrations.starlette_client import OAuth

from app.settings import GITLAB_URL

from .settings import GITLAB_OAUTH, GITLAB_OAUTH_NAME

_MANDATORY_KEYS = ["client_id", "client_secret", "server_metadata_url"]


class GitlabToken(NamedTuple):
    value: str
    query: dict[str, Any]
    rc_query: dict[str, Any]


def init_oauth() -> OAuth:
    _oauth = OAuth()

    gitlab_openid_url = (
        f"{GITLAB_URL.removesuffix('/')}/.well-known/openid-configuration"
    )
    gitlab_oauth_conf = {"server_metadata_url": gitlab_openid_url, **GITLAB_OAUTH}
    if all(k in gitlab_oauth_conf for k in _MANDATORY_KEYS):
        _oauth.register(
            name=GITLAB_OAUTH_NAME,
            client_kwargs={
                "scope": "openid email read_user profile api",
                "timeout": 10.0,
            },
            **gitlab_oauth_conf,
        )
    else:
        msg = "GitLab authentication not configured"
        raise ValueError(msg)
    return _oauth


oauth = init_oauth()
