from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.db.session import get_db
from app.models.enums import PaymentStatus, UserRole
from app.schemas.payments import (
    CollectionSummary,
    PaginatedPaymentResponse,
    PaymentDetailResponse,
    PaymentResponse,
    RecordPayment,
    RentRollResponse,
    StripeCheckoutResponse,
    WaivePayment,
)
from app.services.payment_service import PaymentService

router = APIRouter()

_landlord_or_manager = require_role(UserRole.LANDLORD, UserRole.MANAGER)
_any_authenticated = require_role(UserRole.LANDLORD, UserRole.MANAGER, UserRole.TENANT)
_landlord_only = require_role(UserRole.LANDLORD)


# ── List & summary ──────────────────────────────────────────────


@router.get("", response_model=PaginatedPaymentResponse)
async def list_payments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    payment_status: PaymentStatus | None = Query(None, alias="status"),  # noqa: B008
    property_id: UUID | None = Query(None),  # noqa: B008
    month: date | None = Query(None, description="Filter by month (YYYY-MM-01)"),  # noqa: B008
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PaginatedPaymentResponse:
    service = PaymentService(db)
    return await service.list_payments(
        user, page=page, page_size=page_size, payment_status=payment_status, property_id=property_id, month=month
    )


@router.get("/summary", response_model=CollectionSummary)
async def collection_summary(
    month: date = Query(..., description="Month to summarise (YYYY-MM-01)"),  # noqa: B008
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> CollectionSummary:
    service = PaymentService(db)
    return await service.collection_summary(user, month)


# ── Single payment ──────────────────────────────────────────────


@router.get("/{payment_id}", response_model=PaymentDetailResponse)
async def get_payment(
    payment_id: UUID,
    user: CurrentUser = Depends(_any_authenticated),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PaymentDetailResponse:
    service = PaymentService(db)
    return await service.get_payment(user, payment_id)


@router.post("/{payment_id}/record", response_model=PaymentResponse)
async def record_payment(
    payment_id: UUID,
    data: RecordPayment,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PaymentResponse:
    service = PaymentService(db)
    return await service.record_payment(user, payment_id, data)


@router.patch("/{payment_id}/waive", response_model=PaymentResponse)
async def waive_payment(
    payment_id: UUID,
    data: WaivePayment | None = None,
    user: CurrentUser = Depends(_landlord_only),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PaymentResponse:
    service = PaymentService(db)
    return await service.waive_payment(user, payment_id, notes=data.notes if data else None)


@router.patch("/{payment_id}/waive-late-fee", response_model=PaymentResponse)
async def waive_late_fee(
    payment_id: UUID,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PaymentResponse:
    service = PaymentService(db)
    return await service.waive_late_fee(user, payment_id)


# ── Stripe checkout ─────────────────────────────────────────────


@router.post("/{payment_id}/stripe-checkout", response_model=StripeCheckoutResponse)
async def create_stripe_checkout(
    payment_id: UUID,
    user: CurrentUser = Depends(_any_authenticated),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> StripeCheckoutResponse:
    service = PaymentService(db)
    return await service.create_stripe_checkout(user, payment_id)


# ── Lease payments (tenant view) ────────────────────────────────


@router.get("/lease/{lease_id}", response_model=list[PaymentResponse])
async def lease_payments(
    lease_id: UUID,
    user: CurrentUser = Depends(_any_authenticated),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[PaymentResponse]:
    service = PaymentService(db)
    return await service.lease_payments(user, lease_id)


# ── Rent roll (per-property) ────────────────────────────────────


@router.get("/rent-roll/{property_id}", response_model=RentRollResponse)
async def rent_roll(
    property_id: UUID,
    month: date = Query(..., description="Month for rent roll (YYYY-MM-01)"),  # noqa: B008
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> RentRollResponse:
    service = PaymentService(db)
    return await service.rent_roll(user, property_id, month)
