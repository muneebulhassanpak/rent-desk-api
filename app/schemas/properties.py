from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PropertyType, UnitStatus
from app.utils.sanitize import SanitizedStr

# -- Pagination --


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class PaginatedMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


# -- Property Schemas --


class PropertyCreate(BaseModel):
    name: SanitizedStr = Field(..., min_length=1, max_length=200)
    type: PropertyType = PropertyType.SINGLE_FAMILY
    address_line1: SanitizedStr = Field(..., min_length=1)
    address_line2: SanitizedStr | None = None
    city: SanitizedStr = Field(..., min_length=1)
    state: SanitizedStr | None = None
    postal_code: SanitizedStr | None = None
    country: SanitizedStr = "US"
    cover_photo_url: str | None = None
    year_built: int | None = Field(None, ge=1800, le=2100)
    notes: SanitizedStr | None = None


class PropertyUpdate(BaseModel):
    name: SanitizedStr | None = Field(None, min_length=1, max_length=200)
    type: PropertyType | None = None
    address_line1: SanitizedStr | None = Field(None, min_length=1)
    address_line2: SanitizedStr | None = None
    city: SanitizedStr | None = Field(None, min_length=1)
    state: SanitizedStr | None = None
    postal_code: SanitizedStr | None = None
    country: SanitizedStr | None = None
    cover_photo_url: str | None = None
    year_built: int | None = Field(None, ge=1800, le=2100)
    notes: SanitizedStr | None = None


class UnitSummary(BaseModel):
    total: int = 0
    occupied: int = 0
    vacant: int = 0
    under_maintenance: int = 0
    listed: int = 0
    occupancy_pct: Decimal = Decimal("0")
    monthly_rent_roll: Decimal = Decimal("0")


class PropertyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    name: str
    type: PropertyType
    address_line1: str
    address_line2: str | None
    city: str
    state: str | None
    postal_code: str | None
    country: str
    cover_photo_url: str | None
    year_built: int | None
    notes: str | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class PropertyDetailResponse(PropertyResponse):
    units_summary: UnitSummary = UnitSummary()


class PaginatedPropertyResponse(BaseModel):
    items: list[PropertyResponse]
    meta: PaginatedMeta


# -- Unit Schemas --


class UnitCreate(BaseModel):
    label: SanitizedStr = Field(..., min_length=1, max_length=50)
    bedrooms: Decimal | None = Field(None, ge=0)
    bathrooms: Decimal | None = Field(None, ge=0)
    sqft: int | None = Field(None, ge=0)
    monthly_rent: Decimal = Field(Decimal("0"), ge=0)
    security_deposit: Decimal = Field(Decimal("0"), ge=0)
    status: UnitStatus = UnitStatus.VACANT
    description: SanitizedStr | None = None


class UnitUpdate(BaseModel):
    label: SanitizedStr | None = Field(None, min_length=1, max_length=50)
    bedrooms: Decimal | None = Field(None, ge=0)
    bathrooms: Decimal | None = Field(None, ge=0)
    sqft: int | None = Field(None, ge=0)
    monthly_rent: Decimal | None = Field(None, ge=0)
    security_deposit: Decimal | None = Field(None, ge=0)
    status: UnitStatus | None = None
    description: SanitizedStr | None = None


class UnitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    property_id: UUID
    org_id: UUID
    label: str
    bedrooms: Decimal | None
    bathrooms: Decimal | None
    sqft: int | None
    monthly_rent: Decimal
    security_deposit: Decimal
    status: UnitStatus
    description: str | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class PaginatedUnitResponse(BaseModel):
    items: list[UnitResponse]
    meta: PaginatedMeta
