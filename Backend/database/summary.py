from __future__ import annotations
from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pydantic import BaseModel
import uuid
from datetime import datetime
from database.base import Base


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="summary")


class SummaryResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}


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


class UploadResponse(BaseModel):
    document: DocumentResponse
    summary: SummaryResponse

    model_config = {"from_attributes": True}