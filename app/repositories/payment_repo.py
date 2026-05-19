from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PaymentStatus
from app.models.lease import Lease, LeaseTenant
from app.models.payment import RentPayment
from app.models.property import Property
from app.models.unit import Unit
from app.models.user import User


class PaymentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(
        self,
        org_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
        status: PaymentStatus | None = None,
        property_id: UUID | None = None,
        month: date | None = None,
    ) -> tuple[list[RentPayment], int]:
        stmt = select(RentPayment).join(Lease, RentPayment.lease_id == Lease.id).where(RentPayment.org_id == org_id)

        if status:
            stmt = stmt.where(RentPayment.status == status)
        if property_id:
            stmt = stmt.where(Lease.property_id == property_id)
        if month:
            stmt = stmt.where(
                extract("year", RentPayment.due_date) == month.year,
                extract("month", RentPayment.due_date) == month.month,
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(RentPayment.due_date.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)

        return list(result.scalars().all()), total

    async def get_by_id(self, org_id: UUID, payment_id: UUID) -> RentPayment | None:
        stmt = select(RentPayment).where(RentPayment.id == payment_id, RentPayment.org_id == org_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, payment: RentPayment, data: dict) -> RentPayment:
        for key, value in data.items():
            setattr(payment, key, value)
        await self.db.flush()
        return payment

    async def get_payments_for_lease(self, org_id: UUID, lease_id: UUID) -> list[RentPayment]:
        stmt = (
            select(RentPayment)
            .where(RentPayment.org_id == org_id, RentPayment.lease_id == lease_id)
            .order_by(RentPayment.due_date.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def collection_summary(self, org_id: UUID, month: date) -> dict:
        stmt = select(
            func.coalesce(func.sum(RentPayment.amount_due), Decimal("0")).label("total_expected"),
            func.coalesce(func.sum(RentPayment.amount_paid), Decimal("0")).label("total_collected"),
            func.count()
            .filter(RentPayment.status.in_([PaymentStatus.LATE, PaymentStatus.PARTIAL]))
            .label("late_count"),
        ).where(
            RentPayment.org_id == org_id,
            extract("year", RentPayment.due_date) == month.year,
            extract("month", RentPayment.due_date) == month.month,
        )
        row = (await self.db.execute(stmt)).one()
        return {
            "total_expected": row.total_expected,
            "total_collected": row.total_collected,
            "late_count": row.late_count,
        }

    async def rent_roll(self, org_id: UUID, property_id: UUID, month: date) -> list[dict]:
        """Get per-unit payment status for a property in a given month."""
        # Primary tenant name subquery
        primary_tenant = (
            select(User.full_name)
            .join(LeaseTenant, LeaseTenant.tenant_id == User.id)
            .where(LeaseTenant.lease_id == Lease.id, LeaseTenant.is_primary.is_(True))
            .correlate(Lease)
            .scalar_subquery()
        )

        stmt = (
            select(
                Unit.id.label("unit_id"),
                Unit.label.label("unit_label"),
                Unit.monthly_rent,
                primary_tenant.label("tenant_name"),
                RentPayment.status.label("payment_status"),
                func.coalesce(RentPayment.amount_paid, Decimal("0")).label("amount_paid"),
            )
            .select_from(Unit)
            .outerjoin(
                Lease,
                (Lease.unit_id == Unit.id) & (Lease.status.in_(["active", "expiring_soon"])),
            )
            .outerjoin(
                RentPayment,
                (RentPayment.lease_id == Lease.id)
                & (extract("year", RentPayment.due_date) == month.year)
                & (extract("month", RentPayment.due_date) == month.month),
            )
            .where(Unit.property_id == property_id, Unit.org_id == org_id, Unit.is_archived.is_(False))
            .order_by(Unit.label)
        )
        result = await self.db.execute(stmt)
        return [row._asdict() for row in result.all()]

    async def get_lease_for_payment(self, payment: RentPayment) -> Lease | None:
        stmt = select(Lease).where(Lease.id == payment.lease_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_property_name(self, org_id: UUID, property_id: UUID) -> str | None:
        stmt = select(Property.name).where(Property.id == property_id, Property.org_id == org_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_detail_context(self, payment: RentPayment) -> dict:
        """Get tenant name, unit label, property name for a payment."""
        lease = await self.get_lease_for_payment(payment)
        if not lease:
            return {}

        # Primary tenant name
        tenant_stmt = (
            select(User.full_name)
            .join(LeaseTenant, LeaseTenant.tenant_id == User.id)
            .where(LeaseTenant.lease_id == lease.id, LeaseTenant.is_primary.is_(True))
        )
        tenant_name = (await self.db.execute(tenant_stmt)).scalar_one_or_none()

        # Unit label
        unit_stmt = select(Unit.label).where(Unit.id == lease.unit_id)
        unit_label = (await self.db.execute(unit_stmt)).scalar_one_or_none()

        # Property name
        prop_name = await self.get_property_name(payment.org_id, lease.property_id)

        return {
            "tenant_name": tenant_name,
            "unit_label": unit_label,
            "property_name": prop_name,
        }

    async def get_lease_property_id(self, lease_id: UUID) -> UUID | None:
        stmt = select(Lease.property_id).where(Lease.id == lease_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def is_tenant_on_lease(self, user_id: UUID, lease_id: UUID) -> bool:
        stmt = select(LeaseTenant.tenant_id).where(LeaseTenant.lease_id == lease_id, LeaseTenant.tenant_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None
