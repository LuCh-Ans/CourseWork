from __future__ import annotations
import uuid
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.base import Base
from database.chunk import DocumentChunk
from database.summary import Summary
from config import settings
from pdf_service import process_file, blocks_to_text, create_chunks
from llm.llm_client import summarize
from vector_search import save_chunks


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

    user: Mapped["User"] = relationship(back_populates="documents")
    summary: Mapped["Summary | None"] = relationship(back_populates="document", uselist=False)
    chunks: Mapped[list[DocumentChunk]] = relationship(back_populates="document", cascade="all, delete-orphan")


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
        from sqlalchemy.orm import joinedload
        result = await self.db.execute(
            select(Document)
            .options(joinedload(Document.summary))
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
        from sqlalchemy.orm import joinedload
        result = await self.db.execute(
            select(Document)
            .options(joinedload(Document.summary))
            .where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise LookupError("Document not found.")
        if doc.user_id != user_id:
            raise PermissionError("Access denied.")
        return doc

    async def process_upload(
            self,
            user_id: uuid.UUID,
            original_filename: str,
            saved_as: str,
            file_size_bytes: int,
            raw_bytes: bytes,
    ):
        file_path = Path(settings.UPLOAD_DIR) / saved_as
        blocks = process_file(file_path)
        if not blocks:
            raise ValueError("No text could be extracted.")

        prompt_text = blocks_to_text(blocks)
        summary_text = await summarize(prompt_text)
        if not summary_text:
            raise ValueError("LLM вернул пустой ответ")

        chunks = create_chunks(blocks)

        doc = Document(
            user_id=user_id,
            original_filename=original_filename,
            saved_as=saved_as,
            file_size_bytes=file_size_bytes,
            characters_extracted=len(prompt_text),
            chunks_count=len(chunks),
        )
        self.db.add(doc)
        await self.db.flush()

        await save_chunks(self.db, doc.id, chunks)

        summary = Summary(document_id=doc.id, text=summary_text)
        self.db.add(summary)
        await self.db.commit()
        await self.db.refresh(doc)
        await self.db.refresh(summary)
        return doc, summary