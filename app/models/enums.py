import enum


class UserRole(str, enum.Enum):
    LANDLORD = "landlord"
    MANAGER = "manager"
    TENANT = "tenant"
    VENDOR = "vendor"


class PropertyType(str, enum.Enum):
    SINGLE_FAMILY = "single_family"
    MULTI_UNIT = "multi_unit"
    CONDO = "condo"
    COMMERCIAL = "commercial"


class UnitStatus(str, enum.Enum):
    VACANT = "vacant"
    OCCUPIED = "occupied"
    UNDER_MAINTENANCE = "under_maintenance"
    LISTED = "listed"


class LeaseStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class PaymentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    DUE = "due"
    PAID = "paid"
    LATE = "late"
    PARTIAL = "partial"
    OVERPAID = "overpaid"
    WAIVED = "waived"


class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    CHECK = "check"
    STRIPE = "stripe"
    OTHER = "other"


class TicketStatus(str, enum.Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    IN_PROGRESS = "in_progress"
    AWAITING_PARTS = "awaiting_parts"
    COMPLETED = "completed"
    CLOSED = "closed"
    REOPENED = "reopened"


class TicketPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EMERGENCY = "emergency"


class TicketCategory(str, enum.Enum):
    PLUMBING = "plumbing"
    ELECTRICAL = "electrical"
    HVAC = "hvac"
    APPLIANCE = "appliance"
    STRUCTURAL = "structural"
    OTHER = "other"


class BillingTier(str, enum.Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    PORTFOLIO = "portfolio"


class DocumentScope(str, enum.Enum):
    ORG = "org"
    PROPERTY = "property"
    UNIT = "unit"
    LEASE = "lease"
    TICKET = "ticket"


class AuditAction(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    INVITE = "invite"
    REVOKE = "revoke"
    IMPERSONATE = "impersonate"
    PAYMENT_RECORDED = "payment_recorded"
    TICKET_STATE_CHANGE = "ticket_state_change"
    LEASE_STATE_CHANGE = "lease_state_change"
    FEE_APPLIED = "fee_applied"
