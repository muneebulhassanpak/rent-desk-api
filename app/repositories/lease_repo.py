from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import LeaseStatus
from app.models.lease import Lease, LeaseTenant


class LeaseRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(
        self,
        org_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
        status: LeaseStatus | None = None,
        property_id: UUID | None = None,
    ) -> tuple[list[Lease], int]:
        stmt = select(Lease).where(Lease.org_id == org_id)

        if status:
            stmt = stmt.where(Lease.status == status)
        if property_id:
            stmt = stmt.where(Lease.property_id == property_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(Lease.end_date.asc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)

        return list(result.scalars().all()), total

    async def get_by_id(self, org_id: UUID, lease_id: UUID) -> Lease | None:
        stmt = select(Lease).where(Lease.id == lease_id, Lease.org_id == org_id).options(selectinload(Lease.tenants))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, lease: Lease) -> Lease:
        self.db.add(lease)
        await self.db.flush()
        return lease

    async def add_tenants(self, lease_id: UUID, tenant_ids: list[UUID], primary_tenant_id: UUID) -> None:
        for tid in tenant_ids:
            lt = LeaseTenant(
                lease_id=lease_id,
                tenant_id=tid,
                is_primary=(tid == primary_tenant_id),
                added_at=datetime.now(UTC),
            )
            self.db.add(lt)
        await self.db.flush()

    async def update(self, lease: Lease, data: dict) -> Lease:
        for key, value in data.items():
            if value is not None:
                setattr(lease, key, value)
        await self.db.flush()
        return lease

    async def get_leases_for_tenant(self, org_id: UUID, tenant_id: UUID) -> list[Lease]:
        stmt = (
            select(Lease)
            .join(LeaseTenant, LeaseTenant.lease_id == Lease.id)
            .where(Lease.org_id == org_id, LeaseTenant.tenant_id == tenant_id)
            .order_by(Lease.start_date.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
