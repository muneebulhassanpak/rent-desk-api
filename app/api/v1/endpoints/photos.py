from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.db.session import get_db
from app.models.enums import UserRole
from app.schemas.documents import DocumentResponse
from app.services.photo_service import PhotoService

router = APIRouter()

_landlord_or_manager = require_role(UserRole.LANDLORD, UserRole.MANAGER)


@router.post(
    "/properties/{property_id}/photos",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["photos"],
)
async def upload_property_photo(
    property_id: UUID,
    file: UploadFile,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DocumentResponse:
    service = PhotoService(db)
    return await service.upload_property_photo(user, property_id, file)


@router.get("/properties/{property_id}/photos", response_model=list[DocumentResponse], tags=["photos"])
async def list_property_photos(
    property_id: UUID,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[DocumentResponse]:
    service = PhotoService(db)
    return await service.list_property_photos(user, property_id)


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["photos"])
async def delete_photo(
    photo_id: UUID,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> None:
    service = PhotoService(db)
    await service.delete_photo(user, photo_id)
