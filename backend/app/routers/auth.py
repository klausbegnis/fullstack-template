from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.config import SettingsDep
from app.core.exceptions import UnauthorizedException
from app.core.security import clear_auth_cookies, set_auth_cookies
from app.dependencies import AuthContextDep, AuthServiceDep, CurrentUser
from app.schemas.api.auth import AuthUserRead, LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(
    payload: LoginRequest,
    response: Response,
    context: AuthContextDep,
    service: AuthServiceDep,
    config: SettingsDep,
) -> AuthUserRead:
    del context
    result = await service.login(payload.email, payload.password)
    set_auth_cookies(
        response,
        result.access_token,
        result.refresh_token,
        result.csrf_token,
        config=config,
    )
    return result.user


@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
async def refresh(
    response: Response,
    context: AuthContextDep,
    service: AuthServiceDep,
    config: SettingsDep,
) -> None:
    try:
        result = await service.refresh(context)
    except UnauthorizedException:
        clear_auth_cookies(response, config=config)
        raise
    set_auth_cookies(
        response,
        result.access_token,
        result.refresh_token,
        result.csrf_token,
        config=config,
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
