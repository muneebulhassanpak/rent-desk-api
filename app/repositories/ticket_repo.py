from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import TicketStatus
from app.models.ticket import Ticket, TicketAttachment, TicketEvent
from app.models.user import User


class TicketRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── List queries ─────────────────────────────────────────────

    async def list(
        self,
        org_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
        status: TicketStatus | None = None,
        priority: str | None = None,
        category: str | None = None,
        property_id: UUID | None = None,
        vendor_id: UUID | None = None,
    ) -> tuple[list[Ticket], int]:
        stmt = select(Ticket).where(Ticket.org_id == org_id)

        if status:
            stmt = stmt.where(Ticket.status == status)
        if priority:
            stmt = stmt.where(Ticket.priority == priority)
        if category:
            stmt = stmt.where(Ticket.category == category)
        if property_id:
            stmt = stmt.where(Ticket.property_id == property_id)
        if vendor_id:
            stmt = stmt.where(Ticket.assigned_vendor_id == vendor_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(Ticket.opened_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)

        return list(result.scalars().all()), total

    async def get_my_tickets(self, org_id: UUID, user_id: UUID) -> list[Ticket]:
        stmt = (
            select(Ticket)
            .where(Ticket.org_id == org_id, Ticket.submitted_by == user_id)
            .order_by(Ticket.opened_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_assigned_tickets(self, org_id: UUID, vendor_id: UUID) -> list[Ticket]:
        stmt = (
            select(Ticket)
            .where(
                Ticket.org_id == org_id,
                Ticket.assigned_vendor_id == vendor_id,
                Ticket.status.notin_([TicketStatus.CLOSED]),
            )
            .order_by(Ticket.opened_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── Single ticket ────────────────────────────────────────────

    async def get_by_id(self, org_id: UUID, ticket_id: UUID) -> Ticket | None:
        stmt = (
            select(Ticket)
            .where(Ticket.id == ticket_id, Ticket.org_id == org_id)
            .options(selectinload(Ticket.events), selectinload(Ticket.attachments))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, ticket: Ticket) -> Ticket:
        self.db.add(ticket)
        await self.db.flush()
        return ticket

    async def update(self, ticket: Ticket, data: dict) -> Ticket:
        for key, value in data.items():
            setattr(ticket, key, value)
        await self.db.flush()
        return ticket

    # ── Events ───────────────────────────────────────────────────

    async def add_event(
        self,
        ticket_id: UUID,
        actor_id: UUID,
        event_type: str,
        *,
        from_status: TicketStatus | None = None,
        to_status: TicketStatus | None = None,
        comment: str | None = None,
        metadata: dict | None = None,
    ) -> TicketEvent:
        event = TicketEvent(
            ticket_id=ticket_id,
            actor_id=actor_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            comment=comment,
            metadata_=metadata,
            created_at=datetime.now(UTC),
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def get_events(self, ticket_id: UUID) -> list[TicketEvent]:
        stmt = select(TicketEvent).where(TicketEvent.ticket_id == ticket_id).order_by(TicketEvent.created_at.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── Attachments ──────────────────────────────────────────────

    async def add_attachment(self, attachment: TicketAttachment) -> TicketAttachment:
        self.db.add(attachment)
        await self.db.flush()
        return attachment

    # ── Stats ────────────────────────────────────────────────────

    async def stats(self, org_id: UUID) -> dict[str, int]:
        stmt = select(Ticket.status, func.count().label("cnt")).where(Ticket.org_id == org_id).group_by(Ticket.status)
        rows = (await self.db.execute(stmt)).all()
        counts = {row.status: row.cnt for row in rows}
        return {
            "open": counts.get(TicketStatus.OPEN, 0) + counts.get(TicketStatus.REOPENED, 0),
            "assigned": counts.get(TicketStatus.ASSIGNED, 0),
            "in_progress": counts.get(TicketStatus.IN_PROGRESS, 0),
            "awaiting_parts": counts.get(TicketStatus.AWAITING_PARTS, 0),
            "completed": counts.get(TicketStatus.COMPLETED, 0),
        }

    # ── Detail context ───────────────────────────────────────────

    async def is_vendor_in_org(self, org_id: UUID, vendor_id: UUID) -> bool:
        from app.models.enums import UserRole

        stmt = select(User.id).where(
            User.id == vendor_id, User.org_id == org_id, User.role == UserRole.VENDOR, User.is_active.is_(True)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_detail_context(self, ticket: Ticket) -> dict:
        submitter_name = (
            await self.db.execute(select(User.full_name).where(User.id == ticket.submitted_by))
        ).scalar_one_or_none()

        vendor_name = None
        if ticket.assigned_vendor_id:
            vendor_name = (
                await self.db.execute(select(User.full_name).where(User.id == ticket.assigned_vendor_id))
            ).scalar_one_or_none()

        from app.models.unit import Unit

        unit_label = (await self.db.execute(select(Unit.label).where(Unit.id == ticket.unit_id))).scalar_one_or_none()

        from app.models.property import Property

        prop_name = (
            await self.db.execute(select(Property.name).where(Property.id == ticket.property_id))
        ).scalar_one_or_none()

        return {
            "submitted_by_name": submitter_name,
            "assigned_vendor_name": vendor_name,
            "unit_label": unit_label,
            "property_name": prop_name,
        }
