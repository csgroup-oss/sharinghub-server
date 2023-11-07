from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter
from starlette.status import HTTP_401_UNAUTHORIZED

from app.dependencies import (
    OAuthDep,
    PostCleanSessionDep,
    PreCleanSessionDep,
    SessionAuthDep,
)
from app.utils.http import url_for

router = APIRouter()


@router.get("/info")
async def auth_info(session_auth: SessionAuthDep):
    if session_auth:
        return session_auth
    raise HTTPException(
        status_code=HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


@router.get("/login", dependencies=[PreCleanSessionDep])
async def auth_login(
    request: Request, gitlab: str, oauth: OAuthDep, session_auth: SessionAuthDep
):
    if session_auth:  # Already logged in, redirect
        return RedirectResponse(url_for(request, "index"))

    redirect_uri = url_for(request, "auth_login_callback", path=dict(gitlab=gitlab))
    return await oauth.authorize_redirect(request, redirect_uri)


@router.get("/login/callback", dependencies=[PostCleanSessionDep])
async def auth_login_callback(
    request: Request, session_auth: SessionAuthDep, oauth: OAuthDep
):
    token = await oauth.authorize_access_token(request)
    session_auth["user"] = token.pop("userinfo")
    session_auth["token"] = token
    return RedirectResponse(url_for(request, "index"))


@router.get("/logout")
async def auth_logout(request: Request, session_auth: SessionAuthDep):
    session_auth.clear()
    return RedirectResponse(url_for(request, "index"))
