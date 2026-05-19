from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PaymentMethod, PaymentStatus
from app.schemas.properties import PaginatedMeta
from app.utils.sanitize import SanitizedStr

# -- Request schemas --


class RecordPayment(BaseModel):
    amount: Decimal = Field(..., gt=0)
    payment_date: date
    method: PaymentMethod
    reference: SanitizedStr | None = None
    notes: SanitizedStr | None = None


class WaivePayment(BaseModel):
    notes: SanitizedStr | None = None


# -- Response schemas --


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    lease_id: UUID
    due_date: date
    amount_due: Decimal
    amount_paid: Decimal
    late_fee_amount: Decimal
    late_fee_applied_at: datetime | None
    paid_at: datetime | None
    method: PaymentMethod | None
    reference: str | None
    stripe_payment_intent_id: str | None
    notes: str | None
    recorded_by: UUID | None
    status: PaymentStatus
    created_at: datetime
    updated_at: datetime


class PaymentDetailResponse(PaymentResponse):
    tenant_name: str | None = None
    unit_label: str | None = None
    property_name: str | None = None


class PaginatedPaymentResponse(BaseModel):
    items: list[PaymentResponse]
    meta: PaginatedMeta


class CollectionSummary(BaseModel):
    month: str  # "2026-05"
    total_expected: Decimal
    total_collected: Decimal
    outstanding: Decimal
    late_count: int
    collection_rate: Decimal  # percentage 0-100


class RentRollUnit(BaseModel):
    unit_id: UUID
    unit_label: str
    tenant_name: str | None
    monthly_rent: Decimal
    payment_status: PaymentStatus | None
    amount_paid: Decimal


class RentRollResponse(BaseModel):
    property_id: UUID
    property_name: str
    month: str
    units: list[RentRollUnit]
    total_expected: Decimal
    total_collected: Decimal
    collection_rate: Decimal


class StripeCheckoutResponse(BaseModel):
    checkout_url: str
