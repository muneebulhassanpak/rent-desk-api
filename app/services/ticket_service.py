import math
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.models.enums import TicketStatus, UserRole
from app.models.ticket import Ticket, TicketAttachment
from app.repositories.ticket_repo import TicketRepository
from app.repositories.unit_repo import UnitRepository
from app.schemas.properties import PaginatedMeta
from app.schemas.tickets import (
    ALLOWED_TRANSITIONS,
    PaginatedTicketResponse,
    TicketAssign,
    TicketAttachmentResponse,
    TicketComment,
    TicketCreate,
    TicketDetailResponse,
    TicketEventResponse,
    TicketRate,
    TicketResponse,
    TicketStatsResponse,
    TicketStatusUpdate,
)


class TicketService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = TicketRepository(db)
        self.unit_repo = UnitRepository(db)

    # ── List ─────────────────────────────────────────────────────

    async def list_tickets(
        self,
        user: CurrentUser,
        *,
        page: int = 1,
        page_size: int = 20,
        ticket_status: TicketStatus | None = None,
        priority: str | None = None,
        category: str | None = None,
        property_id: UUID | None = None,
        vendor_id: UUID | None = None,
    ) -> PaginatedTicketResponse:
        items, total = await self.repo.list(
            user.org_id,
            page=page,
            page_size=page_size,
            status=ticket_status,
            priority=priority,
            category=category,
            property_id=property_id,
            vendor_id=vendor_id,
        )
        return PaginatedTicketResponse(
            items=[TicketResponse.model_validate(t) for t in items],
            meta=PaginatedMeta(
                page=page, page_size=page_size, total=total, total_pages=max(1, math.ceil(total / page_size))
            ),
        )

    async def my_tickets(self, user: CurrentUser) -> list[TicketResponse]:
        tickets = await self.repo.get_my_tickets(user.org_id, user.user_id)
        return [TicketResponse.model_validate(t) for t in tickets]

    async def assigned_tickets(self, user: CurrentUser) -> list[TicketResponse]:
        tickets = await self.repo.get_assigned_tickets(user.org_id, user.user_id)
        return [TicketResponse.model_validate(t) for t in tickets]

    async def stats(self, user: CurrentUser) -> TicketStatsResponse:
        raw = await self.repo.stats(user.org_id)
        return TicketStatsResponse(**raw)

    # ── Get detail ───────────────────────────────────────────────

    async def get_ticket(self, user: CurrentUser, ticket_id: UUID) -> TicketDetailResponse:
        ticket = await self._get_and_check_access(user, ticket_id)

        resp = TicketDetailResponse.model_validate(ticket)
        context = await self.repo.get_detail_context(ticket)
        resp.submitted_by_name = context.get("submitted_by_name")
        resp.assigned_vendor_name = context.get("assigned_vendor_name")
        resp.unit_label = context.get("unit_label")
        resp.property_name = context.get("property_name")
        resp.events = [TicketEventResponse.model_validate(e) for e in ticket.events]
        resp.attachments = [TicketAttachmentResponse.model_validate(a) for a in ticket.attachments]
        return resp

    # ── Create ───────────────────────────────────────────────────

    async def create_ticket(self, user: CurrentUser, data: TicketCreate) -> TicketResponse:
        unit = await self.unit_repo.get_by_id(user.org_id, data.unit_id)
        if not unit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")

        if user.role == UserRole.MANAGER and unit.property_id not in user.property_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this property")

        now = datetime.now(UTC)
        ticket = Ticket(
            org_id=user.org_id,
            property_id=unit.property_id,
            unit_id=data.unit_id,
            submitted_by=user.user_id,
            title=data.title,
            description=data.description,
            category=data.category,
            priority=data.priority,
            status=TicketStatus.OPEN,
            opened_at=now,
        )
        ticket = await self.repo.create(ticket)

        await self.repo.add_event(
            ticket.id,
            user.user_id,
            "created",
            to_status=TicketStatus.OPEN,
            comment=data.description,
        )

        return TicketResponse.model_validate(ticket)

    # ── Assign vendor ────────────────────────────────────────────

    async def assign_vendor(self, user: CurrentUser, ticket_id: UUID, data: TicketAssign) -> TicketResponse:
        ticket = await self._get_and_check_access(user, ticket_id)

        if ticket.status not in (TicketStatus.OPEN, TicketStatus.REOPENED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only assign vendor to open or reopened tickets",
            )

        is_vendor = await self.repo.is_vendor_in_org(user.org_id, data.vendor_id)
        if not is_vendor:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid vendor")

        old_status = ticket.status
        now = datetime.now(UTC)
        ticket = await self.repo.update(
            ticket,
            {
                "assigned_vendor_id": data.vendor_id,
                "status": TicketStatus.ASSIGNED,
                "assigned_at": now,
            },
        )

        await self.repo.add_event(
            ticket.id,
            user.user_id,
            "assigned",
            from_status=old_status,
            to_status=TicketStatus.ASSIGNED,
            metadata={"vendor_id": str(data.vendor_id)},
        )

        return TicketResponse.model_validate(ticket)

    # ── Status transition ────────────────────────────────────────

    async def update_status(self, user: CurrentUser, ticket_id: UUID, data: TicketStatusUpdate) -> TicketResponse:
        ticket = await self._get_and_check_access(user, ticket_id)

        role_key = user.role.value
        allowed = ALLOWED_TRANSITIONS.get(ticket.status, {}).get(role_key, [])
        if data.status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot transition from {ticket.status.value} to {data.status.value} as {role_key}",
            )

        old_status = ticket.status
        updates: dict = {"status": data.status}

        # Set timestamps based on new status
        now = datetime.now(UTC)
        if data.status == TicketStatus.ACCEPTED:
            updates["accepted_at"] = now
        elif data.status == TicketStatus.COMPLETED:
            updates["completed_at"] = now
        elif data.status == TicketStatus.CLOSED:
            updates["closed_at"] = now
        elif data.status == TicketStatus.DECLINED or data.status in (TicketStatus.OPEN, TicketStatus.REOPENED):
            updates["assigned_vendor_id"] = None
            updates["assigned_at"] = None

        ticket = await self.repo.update(ticket, updates)

        await self.repo.add_event(
            ticket.id,
            user.user_id,
            "status_change",
            from_status=old_status,
            to_status=data.status,
            comment=data.comment,
        )

        return TicketResponse.model_validate(ticket)

    # ── Comment ──────────────────────────────────────────────────

    async def add_comment(self, user: CurrentUser, ticket_id: UUID, data: TicketComment) -> TicketEventResponse:
        await self._get_and_check_access(user, ticket_id)

        event = await self.repo.add_event(
            ticket_id,
            user.user_id,
            "comment",
            comment=data.comment,
        )
        return TicketEventResponse.model_validate(event)

    # ── Rate ─────────────────────────────────────────────────────

    async def rate_ticket(self, user: CurrentUser, ticket_id: UUID, data: TicketRate) -> TicketResponse:
        ticket = await self._get_and_check_access(user, ticket_id)

        if ticket.status != TicketStatus.CLOSED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only rate closed tickets")

        if ticket.submitted_by != user.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the submitter can rate")

        if ticket.rating is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ticket already rated")

        ticket = await self.repo.update(
            ticket,
            {
                "rating": data.rating,
                "rating_comment": data.comment,
            },
        )

        await self.repo.add_event(
            ticket.id,
            user.user_id,
            "rated",
            metadata={"rating": data.rating},
            comment=data.comment,
        )

        return TicketResponse.model_validate(ticket)

    # ── Attachments ──────────────────────────────────────────────

    async def add_attachments(
        self,
        user: CurrentUser,
        ticket_id: UUID,
        files: list[dict],
    ) -> list[TicketAttachmentResponse]:
        await self._get_and_check_access(user, ticket_id)

        results = []
        now = datetime.now(UTC)
        for f in files:
            att = TicketAttachment(
                ticket_id=ticket_id,
                uploaded_by=user.user_id,
                storage_key=f["storage_key"],
                mime_type=f["mime_type"],
                size_bytes=f["size_bytes"],
                purpose=f.get("purpose", "photo"),
                created_at=now,
            )
            att = await self.repo.add_attachment(att)
            results.append(TicketAttachmentResponse.model_validate(att))

        await self.repo.add_event(
            ticket_id,
            user.user_id,
            "attachment",
            metadata={"count": len(files)},
        )

        return results

    # ── Events ───────────────────────────────────────────────────

    async def get_events(self, user: CurrentUser, ticket_id: UUID) -> list[TicketEventResponse]:
        await self._get_and_check_access(user, ticket_id)
        events = await self.repo.get_events(ticket_id)
        return [TicketEventResponse.model_validate(e) for e in events]

    # ── Access control ───────────────────────────────────────────

    async def _get_and_check_access(self, user: CurrentUser, ticket_id: UUID) -> Ticket:
        ticket = await self.repo.get_by_id(user.org_id, ticket_id)
        if not ticket:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

        if user.role == UserRole.MANAGER and ticket.property_id not in user.property_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this property")

        if user.role == UserRole.TENANT and ticket.submitted_by != user.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your ticket")

        if user.role == UserRole.VENDOR and ticket.assigned_vendor_id != user.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to you")

        return ticket
