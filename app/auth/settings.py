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

from app.settings import conf
from app.utils.config import cbool

GITLAB_ALLOW_PUBLIC: bool = conf(
    "gitlab.allow-public", "GITLAB_ALLOW_PUBLIC", default=False, cast=cbool()
)
_CLIENT_ID: str | None = conf(
    "gitlab.oauth.client-id",
    "GITLAB_OAUTH_CLIENT_ID",
    cast=str,
)
_CLIENT_SECRET: str | None = conf(
    "gitlab.oauth.client-secret",
    "GITLAB_OAUTH_CLIENT_SECRET",
    cast=str,
)
GITLAB_OAUTH = {"client_id": _CLIENT_ID, "client_secret": _CLIENT_SECRET}
GITLAB_OAUTH = {k: v for k, v in GITLAB_OAUTH.items() if v}
GITLAB_OAUTH_DEFAULT_TOKEN: str | None = conf(
    "gitlab.oauth.default-token",
    "GITLAB_OAUTH_DEFAULT_TOKEN",
    cast=str,
)
GITLAB_OAUTH_NAME = "gitlab"

SESSION_AUTH_KEY = "auth"
