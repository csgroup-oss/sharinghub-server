from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter
from starlette.status import HTTP_401_UNAUTHORIZED

from app.config import SESSION_AUTH_KEY
from app.dependencies import OAuthDep, SessionAuthDep, SessionDep
from app.utils.http import url_for

router = APIRouter()


@router.get("/info")
async def auth_info(session_auth: SessionAuthDep):
    if "user" in session_auth:
        return session_auth["user"]
    raise HTTPException(
        status_code=HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


@router.get("/login")
async def auth_login(request: Request, gitlab: str, oauth: OAuthDep):
    redirect_uri = url_for(request, "auth_login_callback", path=dict(gitlab=gitlab))
    return await oauth.authorize_redirect(request, redirect_uri)


@router.get("/login/callback")
async def auth_login_callback(
    request: Request, session_auth: SessionAuthDep, oauth: OAuthDep
):
    token = await oauth.authorize_access_token(request)
    session_auth["token"] = token["access_token"]
    session_auth["user"] = token.pop("userinfo")
    return RedirectResponse(url_for(request, "index"))


@router.get("/logout")
async def auth_logout(request: Request, gitlab: str, session: SessionDep):
    session[SESSION_AUTH_KEY].pop(gitlab)
    return RedirectResponse(url_for(request, "index"))
