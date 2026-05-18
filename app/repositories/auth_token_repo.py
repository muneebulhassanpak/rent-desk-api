import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import AuthToken


class AuthTokenRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def generate_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    async def create(
        self,
        user_id: UUID,
        purpose: str,
        token_hash: str,
        expires_at: datetime,
    ) -> AuthToken:
        at = AuthToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
        )
        self.db.add(at)
        await self.db.flush()
        return at

    async def get_valid_token(self, token_hash: str, purpose: str) -> AuthToken | None:
        stmt = select(AuthToken).where(
            AuthToken.token_hash == token_hash,
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > datetime.now(UTC),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_used(self, auth_token: AuthToken) -> None:
        auth_token.used_at = datetime.now(UTC)
        await self.db.flush()
