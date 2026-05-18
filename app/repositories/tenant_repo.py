from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.models.user import TenantProfile, User


class TenantRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(
        self,
        org_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        active_only: bool = False,
    ) -> tuple[list[User], int]:
        stmt = select(User).where(User.org_id == org_id, User.role == UserRole.TENANT)

        if active_only:
            stmt = stmt.where(User.is_active.is_(True))
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(User.full_name.ilike(pattern) | User.email.ilike(pattern))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(User.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)

        return list(result.scalars().all()), total

    async def get_by_id(self, org_id: UUID, tenant_id: UUID) -> User | None:
        stmt = select(User).where(User.id == tenant_id, User.org_id == org_id, User.role == UserRole.TENANT)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, org_id: UUID, email: str) -> User | None:
        stmt = select(User).where(User.org_id == org_id, User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.db.add(user)
        await self.db.flush()
        return user

    async def update(self, user: User, data: dict) -> User:
        for key, value in data.items():
            if value is not None:
                setattr(user, key, value)
        await self.db.flush()
        return user

    async def deactivate(self, user: User) -> User:
        user.is_active = False
        await self.db.flush()
        return user

    async def get_profile(self, user_id: UUID) -> TenantProfile | None:
        stmt = select(TenantProfile).where(TenantProfile.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_profile(self, user_id: UUID, data: dict) -> TenantProfile:
        profile = await self.get_profile(user_id)
        if not profile:
            profile = TenantProfile(user_id=user_id)
            self.db.add(profile)
        for key, value in data.items():
            if value is not None:
                setattr(profile, key, value)
        await self.db.flush()
        return profile
