import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PaymentMethod, PaymentStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class RentPayment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rent_payments"
    __table_args__ = (UniqueConstraint("lease_id", "due_date"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    lease_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leases.id", ondelete="RESTRICT"), nullable=False
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_due: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    late_fee_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    late_fee_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    method: Mapped[PaymentMethod | None] = mapped_column()
    reference: Mapped[str | None] = mapped_column(Text)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    status: Mapped[PaymentStatus] = mapped_column(default=PaymentStatus.SCHEDULED)

    # Relationships
    lease = relationship("Lease", back_populates="payments")
