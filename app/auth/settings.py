from app.settings import conf

_CLIENT_ID: str | None = conf(
    "gitlab.oauth.client-id", "GITLAB_OAUTH_CLIENT_ID", cast=str
)
_CLIENT_SECRET: str | None = conf(
    "gitlab.oauth.client-secret", "GITLAB_OAUTH_CLIENT_SECRET", cast=str
)
GITLAB_OAUTH = {"client_id": _CLIENT_ID, "client_secret": _CLIENT_SECRET}
GITLAB_OAUTH = {k: v for k, v in GITLAB_OAUTH.items() if v}
GITLAB_OAUTH_DEFAULT_TOKEN: str | None = conf(
    "gitlab.oauth.default-token", "GITLAB_OAUTH_DEFAULT_TOKEN", cast=str
)

SESSION_AUTH_KEY = "auth"
