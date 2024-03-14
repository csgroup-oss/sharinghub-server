from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter
from starlette.status import HTTP_401_UNAUTHORIZED

from app.session import PostCleanSessionDep, PreCleanSessionDep, SessionDep
from app.utils.http import url_for

from .depends import AuthAppDep, SessionAuthDep

router = APIRouter()

REDIRECT_URI_KEY = "redirect_uri"


@router.get("/info")
async def auth_info(session_auth: SessionAuthDep) -> dict:
    if session_auth:
        return session_auth
    raise HTTPException(
        status_code=HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


@router.get("/login", dependencies=[PreCleanSessionDep])
async def auth_login(
    request: Request,
    auth_app: AuthAppDep,
    session: SessionDep,
    session_auth: SessionAuthDep,
    redirect_uri: str = "",
) -> RedirectResponse:
    if not redirect_uri:
        index = True
        redirect_uri = url_for(request, "index")
    else:
        index = False

    if session_auth:  # Already logged in, redirect
        return RedirectResponse(redirect_uri)

    if index:
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

    redirect_uri = session.pop(REDIRECT_URI_KEY, url_for(request, "index"))
    return RedirectResponse(redirect_uri)


@router.get("/logout")
async def auth_logout(
    request: Request, session_auth: SessionAuthDep
) -> RedirectResponse:
    session_auth.clear()
    return RedirectResponse(url_for(request, "index"))
