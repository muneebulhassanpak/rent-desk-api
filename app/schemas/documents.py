from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import DocumentScope


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    scope: DocumentScope
    property_id: UUID | None
    unit_id: UUID | None
    lease_id: UUID | None
    ticket_id: UUID | None
    title: str
    storage_key: str
    mime_type: str
    size_bytes: int
    uploaded_by: UUID | None
    url: str | None = None
    created_at: datetime
