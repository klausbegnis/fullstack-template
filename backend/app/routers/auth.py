from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from app.config import SettingsDep
from app.core.exceptions import (
    RefreshSupersededException,
    UnauthorizedException,
    api_exception_handler,
)
from app.core.security import clear_auth_cookies, set_auth_cookies
from app.dependencies import (
    AuthContextDep,
    AuthServiceDep,
    CurrentUser,
    rate_limited,
)
from app.schemas.api.auth import (
    AuthLoginRead,
    AuthSessionExpiry,
    AuthUserRead,
    LoginRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", dependencies=[Depends(rate_limited("login"))])
async def login(
    payload: LoginRequest,
    response: Response,
    context: AuthContextDep,
    service: AuthServiceDep,
    config: SettingsDep,
) -> AuthLoginRead:
    del context
    result = await service.login(payload.email, payload.password)
    set_auth_cookies(
        response,
        result.access_token,
        result.refresh_token,
        result.csrf_token,
        config=config,
    )
    return AuthLoginRead(
        **result.user.model_dump(),
        access_expires_at=result.access_expires_at,
        session_expires_at=result.session_expires_at,
    )


@router.post("/refresh", response_model=AuthSessionExpiry)
async def refresh(
    request: Request,
    response: Response,
    context: AuthContextDep,
    service: AuthServiceDep,
    config: SettingsDep,
) -> JSONResponse | AuthSessionExpiry:
    try:
        result = await service.refresh(context)
    except RefreshSupersededException as exc:
        return api_exception_handler(request, exc)
    except UnauthorizedException as exc:
        rejection = api_exception_handler(request, exc)
        clear_auth_cookies(rejection, config=config)
        return rejection
    set_auth_cookies(
        response,
        result.access_token,
        result.refresh_token,
        result.csrf_token,
        config=config,
    )
    return AuthSessionExpiry(
        access_expires_at=result.access_expires_at,
        session_expires_at=result.session_expires_at,
    )


@router.get("/me")
async def me(user: CurrentUser, service: AuthServiceDep) -> AuthUserRead:
    return await service.to_auth_user(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    context: AuthContextDep,
    service: AuthServiceDep,
    config: SettingsDep,
) -> None:
    await service.logout(context)
    clear_auth_cookies(response, config=config)
