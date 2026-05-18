from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.models.document import Document
from app.models.enums import DocumentScope, UserRole
from app.repositories.document_repo import DocumentRepository
from app.repositories.property_repo import PropertyRepository
from app.schemas.documents import DocumentResponse
from app.utils.storage import delete_file, get_public_url, upload_file

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


class PhotoService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.doc_repo = DocumentRepository(db)
        self.property_repo = PropertyRepository(db)

    async def upload_property_photo(self, user: CurrentUser, property_id: UUID, file: UploadFile) -> DocumentResponse:
        await self._check_property_access(user, property_id)

        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Accepted: {', '.join(ALLOWED_TYPES)}",
            )

        data = await file.read()
        if len(data) > MAX_SIZE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large (max 10 MB)")

        key = upload_file(data, file.content_type, folder=f"properties/{property_id}")

        doc = Document(
            org_id=user.org_id,
            scope=DocumentScope.PROPERTY,
            property_id=property_id,
            title=file.filename or "photo",
            storage_key=key,
            mime_type=file.content_type,
            size_bytes=len(data),
            uploaded_by=user.user_id,
            created_at=datetime.now(UTC),
        )
        doc = await self.doc_repo.create(doc)
        return self._to_response(doc)

    async def delete_photo(self, user: CurrentUser, photo_id: UUID) -> None:
        doc = await self.doc_repo.get_by_id(user.org_id, photo_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

        if doc.property_id:
            await self._check_property_access(user, doc.property_id)

        delete_file(doc.storage_key)
        await self.doc_repo.delete(doc)

    async def list_property_photos(self, user: CurrentUser, property_id: UUID) -> list[DocumentResponse]:
        await self._check_property_access(user, property_id)
        docs = await self.doc_repo.list_by_property(user.org_id, property_id)
        return [self._to_response(d) for d in docs]

    async def _check_property_access(self, user: CurrentUser, property_id: UUID) -> None:
        prop = await self.property_repo.get_by_id(user.org_id, property_id)
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
        if user.role == UserRole.MANAGER and property_id not in user.property_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this property")

    @staticmethod
    def _to_response(doc: Document) -> DocumentResponse:
        resp = DocumentResponse.model_validate(doc)
        resp.url = get_public_url(doc.storage_key)
        return resp
