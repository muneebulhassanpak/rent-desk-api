import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PropertyType
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Property(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "properties"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[PropertyType] = mapped_column(default=PropertyType.SINGLE_FAMILY)
    address_line1: Mapped[str] = mapped_column(Text, nullable=False)
    address_line2: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str | None] = mapped_column(Text)
    postal_code: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str] = mapped_column(Text, default="US")
    cover_photo_url: Mapped[str | None] = mapped_column(Text)
    year_built: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    org = relationship("Org", back_populates="properties")
    units = relationship("Unit", back_populates="property", cascade="all, delete-orphan")
    managers = relationship(
        "User",
        secondary="manager_property_scopes",
        back_populates="managed_properties",
        primaryjoin="Property.id == ManagerPropertyScope.property_id",
        secondaryjoin="User.id == ManagerPropertyScope.manager_id",
        viewonly=True,
    )


class ManagerPropertyScope(Base):
    __tablename__ = "manager_property_scopes"

    manager_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), primary_key=True
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
