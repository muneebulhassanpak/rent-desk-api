from uuid import UUID

from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.db.session import get_db
from app.models.enums import TicketCategory, TicketPriority, TicketStatus, UserRole
from app.schemas.tickets import (
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
from app.services.ticket_service import TicketService

router = APIRouter()

_landlord_or_manager = require_role(UserRole.LANDLORD, UserRole.MANAGER)
_all_roles = require_role(UserRole.LANDLORD, UserRole.MANAGER, UserRole.TENANT, UserRole.VENDOR)
_tenant_only = require_role(UserRole.TENANT)
_vendor_only = require_role(UserRole.VENDOR)
_can_create = require_role(UserRole.LANDLORD, UserRole.MANAGER, UserRole.TENANT)


# ── List endpoints (must be before /{ticket_id} to avoid conflicts) ──


@router.get("/my", response_model=list[TicketResponse])
async def my_tickets(
    user: CurrentUser = Depends(_tenant_only),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[TicketResponse]:
    service = TicketService(db)
    return await service.my_tickets(user)


@router.get("/assigned", response_model=list[TicketResponse])
async def assigned_tickets(
    user: CurrentUser = Depends(_vendor_only),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[TicketResponse]:
    service = TicketService(db)
    return await service.assigned_tickets(user)


@router.get("/stats", response_model=TicketStatsResponse)
async def ticket_stats(
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TicketStatsResponse:
    service = TicketService(db)
    return await service.stats(user)


@router.get("", response_model=PaginatedTicketResponse)
async def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ticket_status: TicketStatus | None = Query(None, alias="status"),  # noqa: B008
    priority: TicketPriority | None = Query(None),  # noqa: B008
    category: TicketCategory | None = Query(None),  # noqa: B008
    property_id: UUID | None = Query(None),  # noqa: B008
    vendor_id: UUID | None = Query(None),  # noqa: B008
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PaginatedTicketResponse:
    service = TicketService(db)
    return await service.list_tickets(
        user,
        page=page,
        page_size=page_size,
        ticket_status=ticket_status,
        priority=priority.value if priority else None,
        category=category.value if category else None,
        property_id=property_id,
        vendor_id=vendor_id,
    )


# ── Create ───────────────────────────────────────────────────────


@router.post("", response_model=TicketResponse, status_code=201)
async def create_ticket(
    data: TicketCreate,
    user: CurrentUser = Depends(_can_create),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TicketResponse:
    service = TicketService(db)
    return await service.create_ticket(user, data)


# ── Single ticket ────────────────────────────────────────────────


@router.get("/{ticket_id}", response_model=TicketDetailResponse)
async def get_ticket(
    ticket_id: UUID,
    user: CurrentUser = Depends(_all_roles),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TicketDetailResponse:
    service = TicketService(db)
    return await service.get_ticket(user, ticket_id)


@router.patch("/{ticket_id}/assign", response_model=TicketResponse)
async def assign_vendor(
    ticket_id: UUID,
    data: TicketAssign,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TicketResponse:
    service = TicketService(db)
    return await service.assign_vendor(user, ticket_id, data)


@router.patch("/{ticket_id}/status", response_model=TicketResponse)
async def update_status(
    ticket_id: UUID,
    data: TicketStatusUpdate,
    user: CurrentUser = Depends(_all_roles),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TicketResponse:
    service = TicketService(db)
    return await service.update_status(user, ticket_id, data)


@router.post("/{ticket_id}/comments", response_model=TicketEventResponse, status_code=201)
async def add_comment(
    ticket_id: UUID,
    data: TicketComment,
    user: CurrentUser = Depends(_all_roles),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TicketEventResponse:
    service = TicketService(db)
    return await service.add_comment(user, ticket_id, data)


@router.post("/{ticket_id}/rate", response_model=TicketResponse)
async def rate_ticket(
    ticket_id: UUID,
    data: TicketRate,
    user: CurrentUser = Depends(_tenant_only),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TicketResponse:
    service = TicketService(db)
    return await service.rate_ticket(user, ticket_id, data)


@router.post("/{ticket_id}/attachments", response_model=list[TicketAttachmentResponse], status_code=201)
async def add_attachments(
    ticket_id: UUID,
    files: list[UploadFile],
    user: CurrentUser = Depends(_all_roles),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[TicketAttachmentResponse]:
    from fastapi import HTTPException

    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files per upload")

    max_file_size = 10 * 1024 * 1024  # 10 MB
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}

    file_dicts = []
    for f in files:
        if f.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Invalid file type: {f.content_type}")
        content = await f.read()
        if len(content) > max_file_size:
            raise HTTPException(status_code=400, detail=f"File {f.filename} exceeds 10 MB limit")
        # TODO: upload to R2 storage, get storage_key back
        storage_key = f"tickets/{ticket_id}/{f.filename}"
        file_dicts.append(
            {
                "storage_key": storage_key,
                "mime_type": f.content_type,
                "size_bytes": len(content),
                "purpose": "photo",
            }
        )

    service = TicketService(db)
    return await service.add_attachments(user, ticket_id, file_dicts)


@router.get("/{ticket_id}/events", response_model=list[TicketEventResponse])
async def get_events(
    ticket_id: UUID,
    user: CurrentUser = Depends(_all_roles),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[TicketEventResponse]:
    service = TicketService(db)
    return await service.get_events(user, ticket_id)
