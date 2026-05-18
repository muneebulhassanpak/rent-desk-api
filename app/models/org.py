from decimal import Decimal

from sqlalchemy import ARRAY, Boolean, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import BillingTier
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Org(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orgs"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text)
    contact_email: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    timezone: Mapped[str] = mapped_column(Text, default="UTC")
    date_format: Mapped[str] = mapped_column(Text, default="YYYY-MM-DD")

    reminder_days_before: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=[3])
    reminder_days_after: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=[3, 7])

    late_fee_type: Mapped[str] = mapped_column(Text, default="none")
    late_fee_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    late_fee_grace_days: Mapped[int] = mapped_column(Integer, default=5)
    default_lease_months: Mapped[int] = mapped_column(Integer, default=12)
    enforce_2fa_for_managers: Mapped[bool] = mapped_column(Boolean, default=False)

    billing_tier: Mapped[BillingTier] = mapped_column(default=BillingTier.FREE)
    stripe_customer_id: Mapped[str | None] = mapped_column(Text)
    stripe_subscription_id: Mapped[str | None] = mapped_column(Text)
    subscription_status: Mapped[str | None] = mapped_column(Text)

    # Relationships
    users = relationship("User", back_populates="org", cascade="all, delete-orphan")
    properties = relationship("Property", back_populates="org", cascade="all, delete-orphan")
