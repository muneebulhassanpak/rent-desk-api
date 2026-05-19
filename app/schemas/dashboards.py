from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import TicketCategory, TicketPriority, TicketStatus

# -- Shared building blocks --


class RentChartPoint(BaseModel):
    month: str  # "2026-01"
    expected: Decimal
    collected: Decimal


class CategoryCount(BaseModel):
    category: TicketCategory
    count: int


class ActivityItem(BaseModel):
    id: UUID
    entity_type: str  # "payment", "ticket", "lease"
    entity_id: UUID
    action: str  # "recorded_payment", "created_ticket", "renewed_lease", etc.
    actor_name: str | None = None
    summary: str
    occurred_at: datetime


# -- Landlord --


class LandlordDashboard(BaseModel):
    total_properties: int
    total_units: int
    occupied_units: int
    occupancy_pct: Decimal
    rent_expected: Decimal
    rent_collected: Decimal
    open_tickets: int
    expiring_leases: int  # next 60 days
    rent_chart: list[RentChartPoint]
    issues_by_category: list[CategoryCount]
    recent_activity: list[ActivityItem]


# -- Manager --


class TodoItem(BaseModel):
    type: str  # "late_payment", "untriaged_ticket", "expiring_lease", "completed_ticket"
    entity_id: UUID
    label: str
    due_date: date | None = None
    priority: str | None = None  # "red", "orange", "yellow", "blue"


class ManagerDashboard(BaseModel):
    assigned_properties: int
    managed_units: int
    rent_expected: Decimal
    rent_collected: Decimal
    tickets_by_priority: dict[TicketPriority, int]
    todo: list[TodoItem]


# -- Tenant --


class TenantLeaseInfo(BaseModel):
    lease_id: UUID
    property_name: str
    unit_label: str
    lease_end: date
    monthly_rent: Decimal


class TenantPaymentDue(BaseModel):
    payment_id: UUID
    due_date: date
    amount_due: Decimal
    amount_paid: Decimal


class TenantDashboard(BaseModel):
    lease: TenantLeaseInfo | None = None
    next_payment: TenantPaymentDue | None = None
    open_tickets: int
    recent_tickets: list["TenantTicketSummary"] = []


class TenantTicketSummary(BaseModel):
    id: UUID
    title: str
    status: TicketStatus
    opened_at: datetime


# -- Vendor --


class VendorDashboard(BaseModel):
    active_tickets: int
    pending_acceptance: int
    completed_this_month: int
    earnings_this_month: Decimal
    avg_rating: Decimal | None = None
    avg_response_hours: Decimal | None = None
