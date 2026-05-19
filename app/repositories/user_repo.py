from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, org_id: UUID, email: str) -> User | None:
        stmt = select(User).where(User.org_id == org_id, User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email_any_org(self, email: str) -> User | None:
        """For login — user provides email, we find them across orgs.

        If the same email exists in multiple orgs, return the most recently
        active account so login doesn't crash with MultipleResultsFound.
        """
        stmt = (
            select(User)
            .where(User.email == email, User.is_active.is_(True))
            .order_by(User.last_login_at.desc().nulls_last())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.db.add(user)
        await self.db.flush()
        return user

    async def update_last_login(self, user: User) -> None:
        from datetime import UTC, datetime

        user.last_login_at = datetime.now(UTC)
        await self.db.flush()
