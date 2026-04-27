import uuid
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.base import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    saved_as: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    characters_extracted: Mapped[int] = mapped_column(Integer, default=0)
    chunks_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="documents")  # noqa: F821
    summary: Mapped["Summary | None"] = relationship(back_populates="document", uselist=False)  # noqa: F821




class DocumentResponse(BaseModel):
    id: uuid.UUID
    original_filename: str
    file_size_bytes: int
    characters_extracted: int
    chunks_count: int
    uploaded_at: datetime
    has_summary: bool

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int


class DocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_documents(self, user_id: uuid.UUID, offset: int, limit: int):
        result = await self.db.execute(
            select(Document)
            .where(Document.user_id == user_id)
            .offset(offset)
            .limit(limit)
        )
        docs = result.scalars().all()
        count = await self.db.execute(
            select(func.count()).where(Document.user_id == user_id)
        )
        total = count.scalar()
        return docs, total

    async def get_document(self, document_id: uuid.UUID, user_id: uuid.UUID):
        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise LookupError("Document not found.")
        if doc.user_id != user_id:
            raise PermissionError("Access denied.")
        return doc