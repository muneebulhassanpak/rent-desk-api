from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UnitStatus
from app.models.unit import Unit
from app.schemas.properties import UnitSummary


class UnitRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_by_property(
        self,
        org_id: UUID,
        property_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
        include_archived: bool = False,
    ) -> tuple[list[Unit], int]:
        stmt = select(Unit).where(Unit.property_id == property_id, Unit.org_id == org_id)

        if not include_archived:
            stmt = stmt.where(Unit.is_archived.is_(False))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(Unit.label)
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)

        return list(result.scalars().all()), total

    async def get_by_id(self, org_id: UUID, unit_id: UUID) -> Unit | None:
        stmt = select(Unit).where(Unit.id == unit_id, Unit.org_id == org_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, unit: Unit) -> Unit:
        self.db.add(unit)
        await self.db.flush()
        return unit

    async def update(self, unit: Unit, data: dict) -> Unit:
        for key, value in data.items():
            if value is not None:
                setattr(unit, key, value)
        await self.db.flush()
        return unit

    async def archive(self, unit: Unit) -> Unit:
        unit.is_archived = True
        await self.db.flush()
        return unit

    async def get_summary_for_property(self, org_id: UUID, property_id: UUID) -> UnitSummary:
        stmt = select(
            func.count().label("total"),
            func.sum(case((Unit.status == UnitStatus.OCCUPIED, 1), else_=0)).label("occupied"),
            func.sum(case((Unit.status == UnitStatus.VACANT, 1), else_=0)).label("vacant"),
            func.sum(case((Unit.status == UnitStatus.UNDER_MAINTENANCE, 1), else_=0)).label("under_maintenance"),
            func.sum(case((Unit.status == UnitStatus.LISTED, 1), else_=0)).label("listed"),
            func.coalesce(func.sum(Unit.monthly_rent), 0).label("rent_roll"),
        ).where(Unit.property_id == property_id, Unit.org_id == org_id, Unit.is_archived.is_(False))
        row = (await self.db.execute(stmt)).one()

        total = row.total or 0
        occupied = row.occupied or 0
        occupancy = Decimal(str(round(occupied / total * 100, 1))) if total > 0 else Decimal("0")

        return UnitSummary(
            total=total,
            occupied=occupied,
            vacant=row.vacant or 0,
            under_maintenance=row.under_maintenance or 0,
            listed=row.listed or 0,
            occupancy_pct=occupancy,
            monthly_rent_roll=row.rent_roll,
        )
