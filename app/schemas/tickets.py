from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from app.schemas.properties import PaginatedMeta
from app.utils.sanitize import SanitizedStr

# -- State machine: allowed transitions per role --

ALLOWED_TRANSITIONS: dict[TicketStatus, dict[str, list[TicketStatus]]] = {
    TicketStatus.OPEN: {
        "landlord": [TicketStatus.ASSIGNED, TicketStatus.CLOSED],
        "manager": [TicketStatus.ASSIGNED, TicketStatus.CLOSED],
    },
    TicketStatus.ASSIGNED: {
        "landlord": [TicketStatus.OPEN],
        "manager": [TicketStatus.OPEN],
        "vendor": [TicketStatus.ACCEPTED, TicketStatus.DECLINED],
    },
    TicketStatus.ACCEPTED: {
        "vendor": [TicketStatus.IN_PROGRESS],
    },
    TicketStatus.DECLINED: {
        "landlord": [TicketStatus.OPEN],
        "manager": [TicketStatus.OPEN],
    },
    TicketStatus.IN_PROGRESS: {
        "vendor": [TicketStatus.AWAITING_PARTS, TicketStatus.COMPLETED],
    },
    TicketStatus.AWAITING_PARTS: {
        "vendor": [TicketStatus.IN_PROGRESS],
    },
    TicketStatus.COMPLETED: {
        "landlord": [TicketStatus.CLOSED],
        "manager": [TicketStatus.CLOSED],
    },
    TicketStatus.CLOSED: {
        "tenant": [TicketStatus.REOPENED],
    },
    TicketStatus.REOPENED: {
        "landlord": [TicketStatus.ASSIGNED, TicketStatus.CLOSED],
        "manager": [TicketStatus.ASSIGNED, TicketStatus.CLOSED],
    },
}


# -- Request schemas --


class TicketCreate(BaseModel):
    unit_id: UUID
    title: SanitizedStr = Field(..., min_length=1, max_length=200)
    description: SanitizedStr = Field(..., min_length=1, max_length=5000)
    category: TicketCategory
    priority: TicketPriority = TicketPriority.NORMAL


class TicketAssign(BaseModel):
    vendor_id: UUID


class TicketStatusUpdate(BaseModel):
    status: TicketStatus
    comment: SanitizedStr | None = Field(None, max_length=2000)


class TicketComment(BaseModel):
    comment: SanitizedStr = Field(..., min_length=1, max_length=2000)


class TicketRate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: SanitizedStr | None = Field(None, max_length=2000)


# -- Response schemas --


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    property_id: UUID
    unit_id: UUID
    submitted_by: UUID
    assigned_vendor_id: UUID | None
    title: str
    description: str
    category: TicketCategory
    priority: TicketPriority
    status: TicketStatus
    invoice_amount: Decimal | None
    rating: int | None
    rating_comment: str | None
    opened_at: datetime
    assigned_at: datetime | None
    accepted_at: datetime | None
    completed_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TicketDetailResponse(TicketResponse):
    submitted_by_name: str | None = None
    assigned_vendor_name: str | None = None
    unit_label: str | None = None
    property_name: str | None = None
    events: list["TicketEventResponse"] = []
    attachments: list["TicketAttachmentResponse"] = []


class PaginatedTicketResponse(BaseModel):
    items: list[TicketResponse]
    meta: PaginatedMeta


class TicketEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_id: UUID
    actor_id: UUID | None
    event_type: str
    from_status: TicketStatus | None
    to_status: TicketStatus | None
    comment: str | None
    created_at: datetime


class TicketAttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_id: UUID
    uploaded_by: UUID | None
    storage_key: str
    mime_type: str
    size_bytes: int
    purpose: str
    created_at: datetime


class TicketStatsResponse(BaseModel):
    open: int
    assigned: int
    in_progress: int
    awaiting_parts: int
    completed: int
