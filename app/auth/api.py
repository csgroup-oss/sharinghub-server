# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
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
    return _oauth


oauth = init_oauth()
