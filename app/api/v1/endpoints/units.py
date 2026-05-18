from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.db.session import get_db
from app.models.enums import UserRole
from app.schemas.properties import (
    PaginatedUnitResponse,
    UnitCreate,
    UnitResponse,
    UnitUpdate,
)
from app.services.unit_service import UnitService

router = APIRouter()

_landlord_or_manager = require_role(UserRole.LANDLORD, UserRole.MANAGER)


# -- Units nested under properties --


@router.get("/properties/{property_id}/units", response_model=PaginatedUnitResponse, tags=["units"])
async def list_units(
    property_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PaginatedUnitResponse:
    service = UnitService(db)
    return await service.list_units(user, property_id, page=page, page_size=page_size)


@router.post(
    "/properties/{property_id}/units", response_model=UnitResponse, status_code=status.HTTP_201_CREATED, tags=["units"]
)
async def create_unit(
    property_id: UUID,
    data: UnitCreate,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> UnitResponse:
    service = UnitService(db)
    return await service.create_unit(user, property_id, data)


# -- Direct unit access --


@router.get("/units/{unit_id}", response_model=UnitResponse, tags=["units"])
async def get_unit(
    unit_id: UUID,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> UnitResponse:
    service = UnitService(db)
    return await service.get_unit(user, unit_id)


@router.put("/units/{unit_id}", response_model=UnitResponse, tags=["units"])
async def update_unit(
    unit_id: UUID,
    data: UnitUpdate,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> UnitResponse:
    service = UnitService(db)
    return await service.update_unit(user, unit_id, data)


@router.delete("/units/{unit_id}", response_model=UnitResponse, tags=["units"])
async def archive_unit(
    unit_id: UUID,
    user: CurrentUser = Depends(require_role(UserRole.LANDLORD)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> UnitResponse:
    service = UnitService(db)
    return await service.archive_unit(user, unit_id)
