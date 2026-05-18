from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole
from app.schemas.properties import PaginatedMeta
from app.utils.sanitize import SanitizedStr


class TenantInvite(BaseModel):
    email: EmailStr
    full_name: SanitizedStr = Field(..., min_length=1, max_length=200)
    phone: SanitizedStr | None = None


class TenantUpdate(BaseModel):
    full_name: SanitizedStr | None = Field(None, min_length=1, max_length=200)
    phone: SanitizedStr | None = None
    emergency_contact_name: SanitizedStr | None = None
    emergency_contact_phone: SanitizedStr | None = None
    notes: SanitizedStr | None = None


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    email: str
    full_name: str
    phone: str | None
    avatar_url: str | None
    role: UserRole
    is_active: bool
    last_login_at: datetime | None
    last_active_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TenantDetailResponse(TenantResponse):
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    notes: str | None = None
    lease_history: list["LeaseShortResponse"] = []


class PaginatedTenantResponse(BaseModel):
    items: list[TenantResponse]
    meta: PaginatedMeta


# Short lease reference used in tenant detail
class LeaseShortResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    unit_id: UUID
    property_id: UUID
    start_date: str
    end_date: str
    monthly_rent: str
    status: str


# Rebuild model to resolve forward ref
TenantDetailResponse.model_rebuild()
