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

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter
from starlette.status import HTTP_401_UNAUTHORIZED

from app.session import PostCleanSessionDep, PreCleanSessionDep, SessionDep
from app.utils.http import url_for

from .depends import AuthAppDep, GitlabTokenDep, SessionAuthDep
from .settings import GITLAB_OAUTH_DEFAULT_TOKEN

router = APIRouter()

REDIRECT_URI_KEY = "redirect_uri"


@router.get("/info")
async def auth_info(gitlab_token: GitlabTokenDep) -> dict:
    if gitlab_token.value == GITLAB_OAUTH_DEFAULT_TOKEN:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Not authenticated, but server default token is enabled. "
            "Missing user token, either use login, or pass it as header or query",
        )
    return {"access_token": gitlab_token.value}


@router.get("/login", dependencies=[PreCleanSessionDep])
async def auth_login(
    request: Request,
    auth_app: AuthAppDep,
    session: SessionDep,
    session_auth: SessionAuthDep,
    redirect_uri: str = "",
) -> RedirectResponse:
    if not redirect_uri:
        root = True
        redirect_uri = url_for(request, "@root")
    else:
        root = False

    if session_auth:  # Already logged in, redirect
        return RedirectResponse(redirect_uri)

    if root:
        session.pop(REDIRECT_URI_KEY, None)
    else:
        session[REDIRECT_URI_KEY] = redirect_uri

    callback_uri = url_for(request, "auth_login_callback")
    return await auth_app.authorize_redirect(request, redirect_uri=callback_uri)


@router.get("/login/callback", dependencies=[PostCleanSessionDep])
async def auth_login_callback(
    request: Request,
    session: SessionDep,
    session_auth: SessionAuthDep,
    auth_app: AuthAppDep,
) -> RedirectResponse:
    token = await auth_app.authorize_access_token(request)
    session_auth["access_token"] = token.get("access_token")

    redirect_uri = session.pop(REDIRECT_URI_KEY, url_for(request, "@root"))
    return RedirectResponse(redirect_uri)


@router.get("/logout")
async def auth_logout(
    request: Request, session_auth: SessionAuthDep
) -> RedirectResponse:
    session_auth.clear()
    return RedirectResponse(url_for(request, "@root"))
