from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.db.session import get_db
from app.models.enums import LeaseStatus, UserRole
from app.schemas.leases import (
    LeaseCreate,
    LeaseDetailResponse,
    LeaseRenew,
    LeaseResponse,
    LeaseTerminate,
    LeaseUpdate,
    PaginatedLeaseResponse,
)
from app.schemas.payments import PaymentResponse
from app.services.lease_service import LeaseService
from app.services.payment_service import PaymentService

router = APIRouter()

_landlord_or_manager = require_role(UserRole.LANDLORD, UserRole.MANAGER)
_any_authenticated = require_role(UserRole.LANDLORD, UserRole.MANAGER, UserRole.TENANT)


@router.get("", response_model=PaginatedLeaseResponse)
async def list_leases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    lease_status: LeaseStatus | None = Query(None, alias="status"),  # noqa: B008
    property_id: UUID | None = Query(None),  # noqa: B008
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PaginatedLeaseResponse:
    service = LeaseService(db)
    return await service.list_leases(
        user, page=page, page_size=page_size, lease_status=lease_status, property_id=property_id
    )


@router.post("", response_model=LeaseResponse, status_code=status.HTTP_201_CREATED)
async def create_lease(
    data: LeaseCreate,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> LeaseResponse:
    service = LeaseService(db)
    return await service.create_lease(user, data)


@router.get("/{lease_id}", response_model=LeaseDetailResponse)
async def get_lease(
    lease_id: UUID,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> LeaseDetailResponse:
    service = LeaseService(db)
    return await service.get_lease(user, lease_id)


@router.put("/{lease_id}", response_model=LeaseResponse)
async def update_lease(
    lease_id: UUID,
    data: LeaseUpdate,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> LeaseResponse:
    service = LeaseService(db)
    return await service.update_lease(user, lease_id, data)


@router.patch("/{lease_id}/activate", response_model=LeaseResponse)
async def activate_lease(
    lease_id: UUID,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> LeaseResponse:
    service = LeaseService(db)
    return await service.activate_lease(user, lease_id)


@router.post("/{lease_id}/renew", response_model=LeaseResponse, status_code=status.HTTP_201_CREATED)
async def renew_lease(
    lease_id: UUID,
    data: LeaseRenew,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> LeaseResponse:
    service = LeaseService(db)
    return await service.renew_lease(user, lease_id, data)


@router.patch("/{lease_id}/terminate", response_model=LeaseResponse)
async def terminate_lease(
    lease_id: UUID,
    data: LeaseTerminate,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> LeaseResponse:
    service = LeaseService(db)
    return await service.terminate_lease(user, lease_id, data)


@router.get("/{lease_id}/payments", response_model=list[PaymentResponse])
async def lease_payments(
    lease_id: UUID,
    user: CurrentUser = Depends(_any_authenticated),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[PaymentResponse]:
    service = PaymentService(db)
    return await service.lease_payments(user, lease_id)
