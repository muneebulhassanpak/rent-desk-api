from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MagicLinkRequest,
    MagicLinkVerifyRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()


def _client_info(request: Request) -> tuple[str | None, str | None]:
    return request.headers.get("user-agent"), request.client.host if request.client else None


@router.post("/login", response_model=AuthResponse)
async def login(
    data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AuthResponse:
    ua, ip = _client_info(request)
    service = AuthService(db)
    return await service.login(data, user_agent=ua, ip=ip)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AuthResponse:
    service = AuthService(db)
    return await service.register(data)


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
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AuthResponse:
    ua, ip = _client_info(request)
    service = AuthService(db)
    return await service.verify_magic_link(data, user_agent=ua, ip=ip)


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
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MessageResponse:
    service = AuthService(db)
    return await service.reset_password(data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    data: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TokenResponse:
    ua, ip = _client_info(request)
    service = AuthService(db)
    return await service.refresh(data, user_agent=ua, ip=ip)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MessageResponse:
    service = AuthService(db)
    return await service.logout(current_user.user_id)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> UserResponse:
    service = AuthService(db)
    return await service.get_me(current_user.user_id)
