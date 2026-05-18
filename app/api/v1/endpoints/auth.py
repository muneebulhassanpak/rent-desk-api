from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MagicLinkRequest,
    MagicLinkVerifyRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key=ACCESS_COOKIE, path="/", domain=settings.COOKIE_DOMAIN)
    response.delete_cookie(key=REFRESH_COOKIE, path="/api/v1/auth", domain=settings.COOKIE_DOMAIN)


def _client_info(request: Request) -> tuple[str | None, str | None]:
    return request.headers.get("user-agent"), request.client.host if request.client else None


@router.post("/login", response_model=AuthResponse)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AuthResponse:
    ua, ip = _client_info(request)
    service = AuthService(db)
    result = await service.login(data, user_agent=ua, ip=ip)
    _set_auth_cookies(response, result.access_token, result.refresh_token)
    return AuthResponse(user=result.user)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AuthResponse:
    service = AuthService(db)
    result = await service.register(data)
    _set_auth_cookies(response, result.access_token, result.refresh_token)
    return AuthResponse(user=result.user)


@router.post("/magic-link", response_model=MessageResponse)
async def request_magic_link(
    data: MagicLinkRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MessageResponse:
    service = AuthService(db)
    return await service.request_magic_link(data)


@router.post("/magic-link/verify", response_model=AuthResponse)
async def verify_magic_link(
    data: MagicLinkVerifyRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AuthResponse:
    ua, ip = _client_info(request)
    service = AuthService(db)
    result = await service.verify_magic_link(data, user_agent=ua, ip=ip)
    _set_auth_cookies(response, result.access_token, result.refresh_token)
    return AuthResponse(user=result.user)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MessageResponse:
    service = AuthService(db)
    return await service.forgot_password(data)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    data: ResetPasswordRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MessageResponse:
    service = AuthService(db)
    result = await service.reset_password(data)
    _clear_auth_cookies(response)
    return result


@router.post("/refresh", response_model=MessageResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MessageResponse:
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")
    ua, ip = _client_info(request)
    service = AuthService(db)
    result = await service.refresh_from_token(refresh_token, user_agent=ua, ip=ip)
    _set_auth_cookies(response, result.access_token, result.refresh_token)
    return MessageResponse(message="Tokens refreshed")


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MessageResponse:
    service = AuthService(db)
    result = await service.logout(current_user.user_id)
    _clear_auth_cookies(response)
    return result


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> UserResponse:
    service = AuthService(db)
    return await service.get_me(current_user.user_id)
