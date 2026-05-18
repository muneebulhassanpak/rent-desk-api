import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import UnitStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Unit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("property_id", "label"),)

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    bedrooms: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    bathrooms: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    sqft: Mapped[int | None] = mapped_column(Integer)
    monthly_rent: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    security_deposit: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    status: Mapped[UnitStatus] = mapped_column(default=UnitStatus.VACANT)
    description: Mapped[str | None] = mapped_column(Text)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    property = relationship("Property", back_populates="units")
