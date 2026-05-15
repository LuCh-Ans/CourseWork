import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.base import Base


class UserProgress(Base):
    __tablename__ = "user_progress"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    streak_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    study_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chats_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cards_done: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    roadmaps_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activity_map: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, server_default='{}')

    user: Mapped["User"] = relationship(back_populates="progress")