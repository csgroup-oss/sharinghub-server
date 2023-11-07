from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App

from app.config import REMOTES

_oauth = OAuth()
_MANDATORY_KEYS = ["client_id", "client_secret", "server_metadata_url"]


def get_oauth_config(remote_name: str) -> StarletteOAuth2App | None:
    if oauth_client := _oauth.create_client(remote_name):
        return oauth_client

    if remote := REMOTES.get(remote_name):
        oauth_conf = remote.get("oauth", {})
        if all(k in oauth_conf for k in _MANDATORY_KEYS):
            return _oauth.register(
                name=remote_name,
                client_kwargs={
                    "scope": "openid email read_user profile api",
                    "timeout": 10.0,
                },
                **oauth_conf,
            )

    return None
