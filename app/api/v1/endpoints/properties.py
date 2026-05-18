from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.db.session import get_db
from app.models.enums import PropertyType, UserRole
from app.schemas.properties import (
    PaginatedPropertyResponse,
    PropertyCreate,
    PropertyDetailResponse,
    PropertyResponse,
    PropertyUpdate,
)
from app.services.property_service import PropertyService

router = APIRouter()

_landlord_or_manager = require_role(UserRole.LANDLORD, UserRole.MANAGER)


@router.get("", response_model=PaginatedPropertyResponse)
async def list_properties(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    property_type: PropertyType | None = Query(None, alias="type"),  # noqa: B008
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PaginatedPropertyResponse:
    service = PropertyService(db)
    return await service.list_properties(
        user, page=page, page_size=page_size, search=search, property_type=property_type
    )


@router.post("", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    data: PropertyCreate,
    user: CurrentUser = Depends(require_role(UserRole.LANDLORD)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PropertyResponse:
    service = PropertyService(db)
    return await service.create_property(user, data)


@router.get("/{property_id}", response_model=PropertyDetailResponse)
async def get_property(
    property_id: UUID,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PropertyDetailResponse:
    service = PropertyService(db)
    return await service.get_property(user, property_id)


@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: UUID,
    data: PropertyUpdate,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PropertyResponse:
    service = PropertyService(db)
    return await service.update_property(user, property_id, data)


@router.delete("/{property_id}", response_model=PropertyResponse)
async def archive_property(
    property_id: UUID,
    user: CurrentUser = Depends(require_role(UserRole.LANDLORD)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PropertyResponse:
    service = PropertyService(db)
    return await service.archive_property(user, property_id)
