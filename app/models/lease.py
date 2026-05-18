import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import LeaseStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Lease(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leases"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units.id", ondelete="RESTRICT"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    monthly_rent: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    security_deposit: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    payment_due_day: Mapped[int] = mapped_column(Integer, default=1)
    late_fee_override: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[LeaseStatus] = mapped_column(default=LeaseStatus.DRAFT)
    signed_pdf_key: Mapped[str | None] = mapped_column(Text)
    terminated_at: Mapped[date | None] = mapped_column(Date)
    termination_reason: Mapped[str | None] = mapped_column(Text)
    deposit_settlement_notes: Mapped[str | None] = mapped_column(Text)
    renewed_from_lease_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("leases.id"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Relationships
    tenants = relationship("LeaseTenant", back_populates="lease", cascade="all, delete-orphan")
    payments = relationship("RentPayment", back_populates="lease")


class LeaseTenant(Base):
    __tablename__ = "lease_tenants"

    lease_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leases.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    lease = relationship("Lease", back_populates="tenants")
