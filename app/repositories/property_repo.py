from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PropertyType
from app.models.property import Property


class PropertyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(
        self,
        org_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        property_type: PropertyType | None = None,
        include_archived: bool = False,
    ) -> tuple[list[Property], int]:
        stmt = select(Property).where(Property.org_id == org_id)

        if not include_archived:
            stmt = stmt.where(Property.is_archived.is_(False))
        if property_type:
            stmt = stmt.where(Property.type == property_type)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(Property.name.ilike(pattern) | Property.address_line1.ilike(pattern))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(Property.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)

        return list(result.scalars().all()), total

    async def get_by_id(self, org_id: UUID, property_id: UUID) -> Property | None:
        stmt = select(Property).where(Property.id == property_id, Property.org_id == org_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, prop: Property) -> Property:
        self.db.add(prop)
        await self.db.flush()
        return prop

    async def update(self, prop: Property, data: dict) -> Property:
        for key, value in data.items():
            if value is not None:
                setattr(prop, key, value)
        await self.db.flush()
        return prop

    async def archive(self, prop: Property) -> Property:
        prop.is_archived = True
        await self.db.flush()
        return prop

    async def list_for_manager(
        self,
        org_id: UUID,
        property_ids: list[UUID],
        *,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        property_type: PropertyType | None = None,
    ) -> tuple[list[Property], int]:
        """List only properties the manager is assigned to."""
        stmt = select(Property).where(
            Property.org_id == org_id,
            Property.id.in_(property_ids),
            Property.is_archived.is_(False),
        )

        if property_type:
            stmt = stmt.where(Property.type == property_type)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(Property.name.ilike(pattern) | Property.address_line1.ilike(pattern))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(Property.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)

        return list(result.scalars().all()), total
