import math
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.models.enums import UserRole
from app.models.unit import Unit
from app.repositories.property_repo import PropertyRepository
from app.repositories.unit_repo import UnitRepository
from app.schemas.properties import (
    PaginatedMeta,
    PaginatedUnitResponse,
    UnitCreate,
    UnitResponse,
    UnitUpdate,
)


class UnitService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.unit_repo = UnitRepository(db)
        self.property_repo = PropertyRepository(db)

    async def list_units(
        self,
        user: CurrentUser,
        property_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedUnitResponse:
        await self._check_property_access(user, property_id)
        items, total = await self.unit_repo.list_by_property(user.org_id, property_id, page=page, page_size=page_size)
        return PaginatedUnitResponse(
            items=[UnitResponse.model_validate(u) for u in items],
            meta=PaginatedMeta(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=max(1, math.ceil(total / page_size)),
            ),
        )

    async def get_unit(self, user: CurrentUser, unit_id: UUID) -> UnitResponse:
        unit = await self._get_authorized_unit(user, unit_id)
        return UnitResponse.model_validate(unit)

    async def create_unit(self, user: CurrentUser, property_id: UUID, data: UnitCreate) -> UnitResponse:
        await self._check_property_access(user, property_id)
        prop = await self.property_repo.get_by_id(user.org_id, property_id)
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

        unit = Unit(
            property_id=property_id,
            org_id=user.org_id,
            label=data.label,
            bedrooms=data.bedrooms,
            bathrooms=data.bathrooms,
            sqft=data.sqft,
            monthly_rent=data.monthly_rent,
            security_deposit=data.security_deposit,
            status=data.status,
            description=data.description,
        )
        unit = await self.unit_repo.create(unit)
        return UnitResponse.model_validate(unit)

    async def update_unit(self, user: CurrentUser, unit_id: UUID, data: UnitUpdate) -> UnitResponse:
        unit = await self._get_authorized_unit(user, unit_id)
        updates = data.model_dump(exclude_unset=True)
        if not updates:
            return UnitResponse.model_validate(unit)
        unit = await self.unit_repo.update(unit, updates)
        return UnitResponse.model_validate(unit)

    async def archive_unit(self, user: CurrentUser, unit_id: UUID) -> UnitResponse:
        unit = await self._get_authorized_unit(user, unit_id)
        unit = await self.unit_repo.archive(unit)
        return UnitResponse.model_validate(unit)

    async def _check_property_access(self, user: CurrentUser, property_id: UUID) -> None:
        prop = await self.property_repo.get_by_id(user.org_id, property_id)
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
        if user.role == UserRole.MANAGER and property_id not in user.property_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this property")

    async def _get_authorized_unit(self, user: CurrentUser, unit_id: UUID) -> Unit:
        unit = await self.unit_repo.get_by_id(user.org_id, unit_id)
        if not unit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
        if user.role == UserRole.MANAGER and unit.property_id not in user.property_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this property")
        return unit
