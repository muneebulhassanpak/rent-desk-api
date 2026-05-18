from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole
from app.models.org import Org
from app.models.user import User
from app.repositories.auth_token_repo import AuthTokenRepository
from app.repositories.refresh_token_repo import RefreshTokenRepository
from app.repositories.user_repo import UserRepository
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


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.refresh_repo = RefreshTokenRepository(db)
        self.auth_token_repo = AuthTokenRepository(db)

    async def login(self, data: LoginRequest, user_agent: str | None = None, ip: str | None = None) -> AuthResponse:
        user = await self.user_repo.get_by_email_any_org(data.email)
        if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

        await self.user_repo.update_last_login(user)

        return await self._issue_tokens(user, user_agent, ip)

    async def register(self, data: RegisterRequest) -> AuthResponse:
        # Only landlords can self-register; they create a new org
        from app.utils.slug import generate_slug

        slug = generate_slug(data.org_name)
        org = Org(
            name=data.org_name,
            slug=slug,
            contact_email=data.email,
        )
        self.db.add(org)
        await self.db.flush()

        # Check no existing user with this email in the new org
        existing = await self.user_repo.get_by_email(org.id, data.email)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        user = User(
            org_id=org.id,
            email=data.email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            role=UserRole.LANDLORD,
            is_active=True,
            is_email_verified=False,
            totp_enabled=False,
            notification_prefs={},
        )
        await self.user_repo.create(user)

        return await self._issue_tokens(user)

    async def request_magic_link(self, data: MagicLinkRequest) -> MessageResponse:
        """Generate a magic link token for passwordless login (tenant flow)."""
        user = await self.user_repo.get_by_email_any_org(data.email)
        if user:
            raw_token = self.auth_token_repo.generate_token()
            token_hash = self.auth_token_repo.hash_token(raw_token)
            await self.auth_token_repo.create(
                user_id=user.id,
                purpose="magic_link",
                token_hash=token_hash,
                expires_at=datetime.now(UTC) + timedelta(minutes=15),
            )
            # TODO: send email via Resend with the raw_token link

        # Always return success to prevent email enumeration
        return MessageResponse(message="If that email exists, a magic link has been sent")

    async def verify_magic_link(
        self, data: MagicLinkVerifyRequest, user_agent: str | None = None, ip: str | None = None
    ) -> AuthResponse:
        token_hash = self.auth_token_repo.hash_token(data.token)
        auth_token = await self.auth_token_repo.get_valid_token(token_hash, "magic_link")
        if not auth_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

        await self.auth_token_repo.mark_used(auth_token)

        user = await self.user_repo.get_by_id(auth_token.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found or deactivated")

        await self.user_repo.update_last_login(user)

        return await self._issue_tokens(user, user_agent, ip)

    async def forgot_password(self, data: ForgotPasswordRequest) -> MessageResponse:
        user = await self.user_repo.get_by_email_any_org(data.email)
        if user:
            raw_token = self.auth_token_repo.generate_token()
            token_hash = self.auth_token_repo.hash_token(raw_token)
            await self.auth_token_repo.create(
                user_id=user.id,
                purpose="password_reset",
                token_hash=token_hash,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
            # TODO: send password reset email via Resend

        return MessageResponse(message="If that email exists, a reset link has been sent")

    async def reset_password(self, data: ResetPasswordRequest) -> MessageResponse:
        token_hash = self.auth_token_repo.hash_token(data.token)
        auth_token = await self.auth_token_repo.get_valid_token(token_hash, "password_reset")
        if not auth_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

        user = await self.user_repo.get_by_id(auth_token.user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user.password_hash = hash_password(data.new_password)
        await self.auth_token_repo.mark_used(auth_token)
        # Revoke all refresh tokens on password reset
        await self.refresh_repo.revoke_all_for_user(user.id)
        await self.db.flush()

        return MessageResponse(message="Password has been reset successfully")

    async def refresh(
        self, data: RefreshTokenRequest, user_agent: str | None = None, ip: str | None = None
    ) -> TokenResponse:
        token_hash = self.refresh_repo.hash_token(data.refresh_token)
        stored = await self.refresh_repo.get_by_hash(token_hash)
        if not stored:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

        # Rotate: revoke old, issue new
        await self.refresh_repo.revoke(stored)

        user = await self.user_repo.get_by_id(stored.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found or deactivated")

        access = create_access_token(user.id, user.org_id, user.role.value, self._get_property_ids(user))
        raw_refresh = create_refresh_token(user.id)
        new_hash = self.refresh_repo.hash_token(raw_refresh)
        await self.refresh_repo.create(
            user_id=user.id,
            token_hash=new_hash,
            expires_at=datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=user_agent,
            ip_address=ip,
        )

        return TokenResponse(access_token=access, refresh_token=raw_refresh)

    async def logout(self, user_id: UUID) -> MessageResponse:
        await self.refresh_repo.revoke_all_for_user(user_id)
        return MessageResponse(message="Logged out successfully")

    async def get_me(self, user_id: UUID) -> UserResponse:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return UserResponse.model_validate(user)

    # -- Helpers --

    async def _issue_tokens(self, user: User, user_agent: str | None = None, ip: str | None = None) -> AuthResponse:
        property_ids = self._get_property_ids(user)
        access = create_access_token(user.id, user.org_id, user.role.value, property_ids)
        raw_refresh = create_refresh_token(user.id)
        refresh_hash = self.refresh_repo.hash_token(raw_refresh)

        await self.refresh_repo.create(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=user_agent,
            ip_address=ip,
        )

        return AuthResponse(
            user=UserResponse.model_validate(user),
            access_token=access,
            refresh_token=raw_refresh,
        )

    @staticmethod
    def _get_property_ids(user: User) -> list[UUID] | None:
        if user.role == UserRole.MANAGER:
            # Load from manager_property_scopes — for now return None (populated later)
            return None
        return None
