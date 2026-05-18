from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document


class DocumentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, doc: Document) -> Document:
        self.db.add(doc)
        await self.db.flush()
        return doc

    async def get_by_id(self, org_id: UUID, doc_id: UUID) -> Document | None:
        stmt = select(Document).where(Document.id == doc_id, Document.org_id == org_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_property(self, org_id: UUID, property_id: UUID) -> list[Document]:
        stmt = (
            select(Document)
            .where(Document.org_id == org_id, Document.property_id == property_id)
            .order_by(Document.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, doc: Document) -> None:
        await self.db.delete(doc)
        await self.db.flush()
