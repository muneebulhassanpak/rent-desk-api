from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import extract, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LeaseStatus, PaymentStatus, TicketStatus, UnitStatus
from app.models.lease import Lease, LeaseTenant
from app.models.payment import RentPayment
from app.models.property import Property
from app.models.ticket import Ticket
from app.models.unit import Unit
from app.models.user import User


class DashboardRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Landlord ──────────────────────────────────────────────────

    async def landlord_kpis(self, org_id: UUID) -> dict:
        # Properties + units
        prop_count = (
            await self.db.execute(
                select(func.count())
                .select_from(Property)
                .where(Property.org_id == org_id, Property.is_archived.is_(False))
            )
        ).scalar_one()

        unit_q = select(func.count(), func.count().filter(Unit.status == UnitStatus.OCCUPIED)).where(
            Unit.org_id == org_id, Unit.is_archived.is_(False)
        )
        total_units, occupied = (await self.db.execute(unit_q)).one()

        occupancy = Decimal(str(round(occupied / total_units * 100, 1))) if total_units > 0 else Decimal("0")

        # Rent this month
        today = date.today()
        month_start = today.replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)

        rent_q = select(
            func.coalesce(func.sum(RentPayment.amount_due), 0),
            func.coalesce(func.sum(RentPayment.amount_paid), 0),
        ).where(
            RentPayment.org_id == org_id,
            RentPayment.due_date >= month_start,
            RentPayment.due_date < next_month,
        )
        expected, collected = (await self.db.execute(rent_q)).one()

        # Open tickets
        open_tickets = (
            await self.db.execute(
                select(func.count())
                .select_from(Ticket)
                .where(
                    Ticket.org_id == org_id,
                    Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REOPENED]),
                )
            )
        ).scalar_one()

        # Expiring leases (next 60 days)
        cutoff = today + timedelta(days=60)
        expiring = (
            await self.db.execute(
                select(func.count())
                .select_from(Lease)
                .where(
                    Lease.org_id == org_id,
                    Lease.status.in_([LeaseStatus.ACTIVE, LeaseStatus.EXPIRING_SOON]),
                    Lease.end_date <= cutoff,
                    Lease.end_date >= today,
                )
            )
        ).scalar_one()

        return {
            "total_properties": prop_count,
            "total_units": total_units,
            "occupied_units": occupied,
            "occupancy_pct": occupancy,
            "rent_expected": expected,
            "rent_collected": collected,
            "open_tickets": open_tickets,
            "expiring_leases": expiring,
        }

    async def rent_chart(self, org_id: UUID, months: int = 12) -> list[dict]:
        today = date.today()
        start = (today.replace(day=1) - timedelta(days=30 * (months - 1))).replace(day=1)

        stmt = (
            select(
                extract("year", RentPayment.due_date).label("yr"),
                extract("month", RentPayment.due_date).label("mo"),
                func.coalesce(func.sum(RentPayment.amount_due), 0).label("expected"),
                func.coalesce(func.sum(RentPayment.amount_paid), 0).label("collected"),
            )
            .where(RentPayment.org_id == org_id, RentPayment.due_date >= start)
            .group_by("yr", "mo")
            .order_by("yr", "mo")
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            {
                "month": f"{int(r.yr)}-{int(r.mo):02d}",
                "expected": r.expected,
                "collected": r.collected,
            }
            for r in rows
        ]

    async def issues_by_category(self, org_id: UUID) -> list[dict]:
        cutoff = datetime.now(UTC) - timedelta(days=90)
        stmt = (
            select(Ticket.category, func.count().label("cnt"))
            .where(Ticket.org_id == org_id, Ticket.opened_at >= cutoff)
            .group_by(Ticket.category)
        )
        rows = (await self.db.execute(stmt)).all()
        return [{"category": r.category, "count": r.cnt} for r in rows]

    async def recent_activity(
        self, org_id: UUID, *, limit: int = 10, property_ids: list[UUID] | None = None
    ) -> list[dict]:
        """Merge recent events from payments and tickets into a single feed."""
        actor_name = (
            select(User.full_name).where(User.id == RentPayment.recorded_by).correlate(RentPayment).scalar_subquery()
        )

        payment_q = select(
            RentPayment.id.label("id"),
            literal("payment").label("entity_type"),
            RentPayment.id.label("entity_id"),
            literal("recorded_payment").label("action"),
            actor_name.label("actor_name"),
            func.concat("Payment of $", func.cast(RentPayment.amount_paid, func.text())).label("summary"),
            RentPayment.paid_at.label("occurred_at"),
        ).where(RentPayment.org_id == org_id, RentPayment.paid_at.isnot(None))

        if property_ids is not None:
            payment_q = payment_q.join(Lease, RentPayment.lease_id == Lease.id).where(
                Lease.property_id.in_(property_ids)
            )

        ticket_actor = select(User.full_name).where(User.id == Ticket.submitted_by).correlate(Ticket).scalar_subquery()

        ticket_q = select(
            Ticket.id.label("id"),
            literal("ticket").label("entity_type"),
            Ticket.id.label("entity_id"),
            literal("created_ticket").label("action"),
            ticket_actor.label("actor_name"),
            func.concat("Ticket: ", Ticket.title).label("summary"),
            Ticket.opened_at.label("occurred_at"),
        ).where(Ticket.org_id == org_id)

        if property_ids is not None:
            ticket_q = ticket_q.where(Ticket.property_id.in_(property_ids))

        combined = union_all(payment_q, ticket_q).subquery()
        stmt = select(combined).order_by(combined.c.occurred_at.desc()).limit(limit)
        rows = (await self.db.execute(stmt)).all()

        return [
            {
                "id": r.id,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "action": r.action,
                "actor_name": r.actor_name,
                "summary": r.summary,
                "occurred_at": r.occurred_at,
            }
            for r in rows
        ]

    # ── Manager ───────────────────────────────────────────────────

    async def manager_kpis(self, org_id: UUID, property_ids: list[UUID]) -> dict:
        if not property_ids:
            return {
                "assigned_properties": 0,
                "managed_units": 0,
                "rent_expected": Decimal("0"),
                "rent_collected": Decimal("0"),
                "tickets_by_priority": {},
            }

        unit_count = (
            await self.db.execute(
                select(func.count())
                .select_from(Unit)
                .where(
                    Unit.org_id == org_id,
                    Unit.property_id.in_(property_ids),
                    Unit.is_archived.is_(False),
                )
            )
        ).scalar_one()

        today = date.today()
        month_start = today.replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)

        rent_q = (
            select(
                func.coalesce(func.sum(RentPayment.amount_due), 0),
                func.coalesce(func.sum(RentPayment.amount_paid), 0),
            )
            .join(Lease, RentPayment.lease_id == Lease.id)
            .where(
                RentPayment.org_id == org_id,
                Lease.property_id.in_(property_ids),
                RentPayment.due_date >= month_start,
                RentPayment.due_date < next_month,
            )
        )
        expected, collected = (await self.db.execute(rent_q)).one()

        # Tickets by priority
        ticket_q = (
            select(Ticket.priority, func.count().label("cnt"))
            .where(
                Ticket.org_id == org_id,
                Ticket.property_id.in_(property_ids),
                Ticket.status.notin_([TicketStatus.CLOSED]),
            )
            .group_by(Ticket.priority)
        )
        rows = (await self.db.execute(ticket_q)).all()
        by_priority = {r.priority: r.cnt for r in rows}

        return {
            "assigned_properties": len(property_ids),
            "managed_units": unit_count,
            "rent_expected": expected,
            "rent_collected": collected,
            "tickets_by_priority": by_priority,
        }

    async def manager_todo(self, org_id: UUID, property_ids: list[UUID]) -> list[dict]:
        if not property_ids:
            return []

        items: list[dict] = []
        today = date.today()

        # Late payments
        late_q = (
            select(RentPayment.id, RentPayment.due_date)
            .join(Lease, RentPayment.lease_id == Lease.id)
            .where(
                RentPayment.org_id == org_id,
                Lease.property_id.in_(property_ids),
                RentPayment.status == PaymentStatus.LATE,
            )
            .limit(20)
        )
        for row in (await self.db.execute(late_q)).all():
            items.append(
                {
                    "type": "late_payment",
                    "entity_id": row.id,
                    "label": f"Late payment due {row.due_date}",
                    "due_date": row.due_date,
                    "priority": "red",
                }
            )

        # Untriaged tickets (open, no vendor assigned)
        untriaged_q = (
            select(Ticket.id, Ticket.title)
            .where(
                Ticket.org_id == org_id,
                Ticket.property_id.in_(property_ids),
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REOPENED]),
                Ticket.assigned_vendor_id.is_(None),
            )
            .limit(20)
        )
        for row in (await self.db.execute(untriaged_q)).all():
            items.append(
                {
                    "type": "untriaged_ticket",
                    "entity_id": row.id,
                    "label": f"Triage: {row.title}",
                    "priority": "orange",
                }
            )

        # Expiring leases (60 days)
        cutoff = today + timedelta(days=60)
        expiring_q = (
            select(Lease.id, Lease.end_date)
            .where(
                Lease.org_id == org_id,
                Lease.property_id.in_(property_ids),
                Lease.status.in_([LeaseStatus.ACTIVE, LeaseStatus.EXPIRING_SOON]),
                Lease.end_date <= cutoff,
                Lease.end_date >= today,
            )
            .limit(20)
        )
        for row in (await self.db.execute(expiring_q)).all():
            items.append(
                {
                    "type": "expiring_lease",
                    "entity_id": row.id,
                    "label": f"Lease expires {row.end_date}",
                    "due_date": row.end_date,
                    "priority": "yellow",
                }
            )

        # Completed tickets to close
        completed_q = (
            select(Ticket.id, Ticket.title)
            .where(
                Ticket.org_id == org_id,
                Ticket.property_id.in_(property_ids),
                Ticket.status == TicketStatus.COMPLETED,
            )
            .limit(20)
        )
        for row in (await self.db.execute(completed_q)).all():
            items.append(
                {
                    "type": "completed_ticket",
                    "entity_id": row.id,
                    "label": f"Close: {row.title}",
                    "priority": "blue",
                }
            )

        return items

    # ── Tenant ────────────────────────────────────────────────────

    async def tenant_dashboard(self, org_id: UUID, user_id: UUID) -> dict:
        # Find active lease for this tenant
        lease_q = (
            select(Lease, Property.name.label("property_name"), Unit.label.label("unit_label"))
            .join(LeaseTenant, LeaseTenant.lease_id == Lease.id)
            .join(Property, Property.id == Lease.property_id)
            .join(Unit, Unit.id == Lease.unit_id)
            .where(
                Lease.org_id == org_id,
                LeaseTenant.tenant_id == user_id,
                Lease.status.in_([LeaseStatus.ACTIVE, LeaseStatus.EXPIRING_SOON]),
            )
            .order_by(Lease.end_date.desc())
            .limit(1)
        )
        lease_row = (await self.db.execute(lease_q)).first()

        lease_info = None
        next_payment = None

        if lease_row:
            lease = lease_row.Lease
            lease_info = {
                "lease_id": lease.id,
                "property_name": lease_row.property_name,
                "unit_label": lease_row.unit_label,
                "lease_end": lease.end_date,
                "monthly_rent": lease.monthly_rent,
            }

            # Next unpaid payment
            pay_q = (
                select(RentPayment)
                .where(
                    RentPayment.lease_id == lease.id,
                    RentPayment.status.in_(
                        [
                            PaymentStatus.DUE,
                            PaymentStatus.SCHEDULED,
                            PaymentStatus.LATE,
                            PaymentStatus.PARTIAL,
                        ]
                    ),
                )
                .order_by(RentPayment.due_date.asc())
                .limit(1)
            )
            pay_row = (await self.db.execute(pay_q)).scalar_one_or_none()
            if pay_row:
                next_payment = {
                    "payment_id": pay_row.id,
                    "due_date": pay_row.due_date,
                    "amount_due": pay_row.amount_due,
                    "amount_paid": pay_row.amount_paid,
                }

        # Open tickets count
        open_tickets = (
            await self.db.execute(
                select(func.count())
                .select_from(Ticket)
                .where(
                    Ticket.org_id == org_id,
                    Ticket.submitted_by == user_id,
                    Ticket.status.notin_([TicketStatus.CLOSED]),
                )
            )
        ).scalar_one()

        # Recent tickets (last 5)
        recent_q = (
            select(Ticket.id, Ticket.title, Ticket.status, Ticket.opened_at)
            .where(Ticket.org_id == org_id, Ticket.submitted_by == user_id)
            .order_by(Ticket.opened_at.desc())
            .limit(5)
        )
        recent = [
            {"id": r.id, "title": r.title, "status": r.status, "opened_at": r.opened_at}
            for r in (await self.db.execute(recent_q)).all()
        ]

        return {
            "lease": lease_info,
            "next_payment": next_payment,
            "open_tickets": open_tickets,
            "recent_tickets": recent,
        }

    # ── Vendor ────────────────────────────────────────────────────

    async def vendor_dashboard(self, org_id: UUID, user_id: UUID) -> dict:
        # Active tickets (not closed)
        active = (
            await self.db.execute(
                select(func.count())
                .select_from(Ticket)
                .where(
                    Ticket.org_id == org_id,
                    Ticket.assigned_vendor_id == user_id,
                    Ticket.status.notin_([TicketStatus.CLOSED, TicketStatus.DECLINED]),
                )
            )
        ).scalar_one()

        # Pending acceptance (assigned but not yet accepted)
        pending = (
            await self.db.execute(
                select(func.count())
                .select_from(Ticket)
                .where(
                    Ticket.org_id == org_id,
                    Ticket.assigned_vendor_id == user_id,
                    Ticket.status == TicketStatus.ASSIGNED,
                )
            )
        ).scalar_one()

        # This month stats
        today = date.today()
        month_start = today.replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)

        monthly_q = select(
            func.count().label("completed"),
            func.coalesce(func.sum(Ticket.invoice_amount), 0).label("earnings"),
        ).where(
            Ticket.org_id == org_id,
            Ticket.assigned_vendor_id == user_id,
            Ticket.completed_at >= datetime(month_start.year, month_start.month, month_start.day, tzinfo=UTC),
            Ticket.completed_at < datetime(next_month.year, next_month.month, next_month.day, tzinfo=UTC),
        )
        monthly = (await self.db.execute(monthly_q)).one()

        # Performance: avg rating + avg response time
        perf_q = select(
            func.avg(Ticket.rating).label("avg_rating"),
        ).where(
            Ticket.org_id == org_id,
            Ticket.assigned_vendor_id == user_id,
            Ticket.rating.isnot(None),
        )
        avg_rating = (await self.db.execute(perf_q)).scalar_one()

        # Avg response hours: from assigned_at to accepted_at
        resp_q = select(
            func.avg(extract("epoch", Ticket.accepted_at - Ticket.assigned_at) / 3600).label("avg_hours"),
        ).where(
            Ticket.org_id == org_id,
            Ticket.assigned_vendor_id == user_id,
            Ticket.accepted_at.isnot(None),
            Ticket.assigned_at.isnot(None),
        )
        avg_hours = (await self.db.execute(resp_q)).scalar_one()

        return {
            "active_tickets": active,
            "pending_acceptance": pending,
            "completed_this_month": monthly.completed,
            "earnings_this_month": monthly.earnings,
            "avg_rating": Decimal(str(round(avg_rating, 2))) if avg_rating else None,
            "avg_response_hours": Decimal(str(round(avg_hours, 1))) if avg_hours else None,
        }

    # ── Activity feed (shared) ────────────────────────────────────

    async def activity_feed(
        self, org_id: UUID, *, limit: int = 20, property_ids: list[UUID] | None = None
    ) -> list[dict]:
        """General activity feed — optionally scoped to specific properties."""
        return await self.recent_activity(org_id, limit=limit, property_ids=property_ids)
