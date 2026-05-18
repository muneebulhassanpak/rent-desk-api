import math
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.models.enums import PropertyType, UserRole
from app.models.property import Property
from app.repositories.property_repo import PropertyRepository
from app.repositories.unit_repo import UnitRepository
from app.schemas.properties import (
    PaginatedMeta,
    PaginatedPropertyResponse,
    PropertyCreate,
    PropertyDetailResponse,
    PropertyResponse,
    PropertyUpdate,
)


class PropertyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = PropertyRepository(db)
        self.unit_repo = UnitRepository(db)

    async def list_properties(
        self,
        user: CurrentUser,
        *,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        property_type: PropertyType | None = None,
    ) -> PaginatedPropertyResponse:
        if user.role == UserRole.MANAGER:
            items, total = await self.repo.list_for_manager(
                user.org_id,
                user.property_ids,
                page=page,
                page_size=page_size,
                search=search,
                property_type=property_type,
            )
        else:
            items, total = await self.repo.list(
                user.org_id,
                page=page,
                page_size=page_size,
                search=search,
                property_type=property_type,
            )

        return PaginatedPropertyResponse(
            items=[PropertyResponse.model_validate(p) for p in items],
            meta=PaginatedMeta(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=max(1, math.ceil(total / page_size)),
            ),
        )

    async def get_property(self, user: CurrentUser, property_id: UUID) -> PropertyDetailResponse:
        prop = await self._get_authorized_property(user, property_id)
        summary = await self.unit_repo.get_summary_for_property(user.org_id, property_id)
        resp = PropertyDetailResponse.model_validate(prop)
        resp.units_summary = summary
        return resp

    async def create_property(self, user: CurrentUser, data: PropertyCreate) -> PropertyResponse:
        prop = Property(
            org_id=user.org_id,
            name=data.name,
            type=data.type,
            address_line1=data.address_line1,
            address_line2=data.address_line2,
            city=data.city,
            state=data.state,
            postal_code=data.postal_code,
            country=data.country,
            cover_photo_url=data.cover_photo_url,
            year_built=data.year_built,
            notes=data.notes,
        )
        prop = await self.repo.create(prop)
        return PropertyResponse.model_validate(prop)

    async def update_property(self, user: CurrentUser, property_id: UUID, data: PropertyUpdate) -> PropertyResponse:
        prop = await self._get_authorized_property(user, property_id)
        updates = data.model_dump(exclude_unset=True)
        if not updates:
            return PropertyResponse.model_validate(prop)
        prop = await self.repo.update(prop, updates)
        return PropertyResponse.model_validate(prop)

    async def archive_property(self, user: CurrentUser, property_id: UUID) -> PropertyResponse:
        prop = await self._get_authorized_property(user, property_id)
        prop = await self.repo.archive(prop)
        return PropertyResponse.model_validate(prop)

    async def _get_authorized_property(self, user: CurrentUser, property_id: UUID) -> Property:
        prop = await self.repo.get_by_id(user.org_id, property_id)
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
        if user.role == UserRole.MANAGER and property_id not in user.property_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this property")
        return prop
