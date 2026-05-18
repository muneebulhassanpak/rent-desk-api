from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import LeaseStatus
from app.schemas.properties import PaginatedMeta
from app.utils.sanitize import SanitizedStr


class LeaseCreate(BaseModel):
    unit_id: UUID
    tenant_ids: list[UUID] = Field(..., min_length=1)
    primary_tenant_id: UUID
    start_date: date
    end_date: date
    monthly_rent: Decimal = Field(..., gt=0)
    security_deposit: Decimal = Field(Decimal("0"), ge=0)
    payment_due_day: int = Field(1, ge=1, le=28)
    notes: SanitizedStr | None = None

    @model_validator(mode="after")
    def validate_dates_and_primary(self) -> "LeaseCreate":
        if self.end_date <= self.start_date:
            msg = "end_date must be after start_date"
            raise ValueError(msg)
        if self.primary_tenant_id not in self.tenant_ids:
            msg = "primary_tenant_id must be in tenant_ids"
            raise ValueError(msg)
        return self


class LeaseUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    monthly_rent: Decimal | None = Field(None, gt=0)
    security_deposit: Decimal | None = Field(None, ge=0)
    payment_due_day: int | None = Field(None, ge=1, le=28)
    notes: SanitizedStr | None = None


class LeaseRenew(BaseModel):
    start_date: date
    end_date: date
    monthly_rent: Decimal = Field(..., gt=0)
    security_deposit: Decimal | None = None
    payment_due_day: int | None = Field(None, ge=1, le=28)

    @model_validator(mode="after")
    def validate_dates(self) -> "LeaseRenew":
        if self.end_date <= self.start_date:
            msg = "end_date must be after start_date"
            raise ValueError(msg)
        return self


class LeaseTerminate(BaseModel):
    termination_date: date
    reason: SanitizedStr | None = None
    deposit_settlement_notes: SanitizedStr | None = None


class LeaseTenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: UUID
    is_primary: bool
    full_name: str | None = None
    email: str | None = None


class LeaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    property_id: UUID
    unit_id: UUID
    start_date: date
    end_date: date
    monthly_rent: Decimal
    security_deposit: Decimal
    payment_due_day: int
    status: LeaseStatus
    terminated_at: date | None
    termination_reason: str | None
    deposit_settlement_notes: str | None
    renewed_from_lease_id: UUID | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class LeaseDetailResponse(LeaseResponse):
    tenants: list[LeaseTenantResponse] = []
    unit_label: str | None = None
    property_name: str | None = None


class PaginatedLeaseResponse(BaseModel):
    items: list[LeaseResponse]
    meta: PaginatedMeta
