import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, selectinload
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.base import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                                               nullable=False)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True),
                                                             ForeignKey("documents.id", ondelete="SET NULL"),
                                                             nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Новый чат")

    # Новые поля для карточек и роадмапа
    cards: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSONB, nullable=True, default=None)
    roadmap: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSONB, nullable=True, default=None)
    card_index: Mapped[Optional[int]] = mapped_column(default=0)
    card_wrong: Mapped[Optional[int]] = mapped_column(default=0)
    card_right: Mapped[Optional[int]] = mapped_column(default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now(), nullable=False)

    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                                                  ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


# ====================== SCHEMAS ======================

class MessageSchema(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    class Config: from_attributes = True


class SessionSchema(BaseModel):
    id: uuid.UUID
    title: str
    document_id: Optional[uuid.UUID] = None
    cards: Optional[List[Dict]] = None
    roadmap: Optional[List[Dict]] = None
    card_index: Optional[int] = 0
    card_wrong: Optional[int] = 0
    card_right: Optional[int] = 0
    created_at: datetime
    updated_at: datetime
    messages: list[MessageSchema] = []

    class Config: from_attributes = True


class SessionListItem(BaseModel):
    id: uuid.UUID
    title: str
    document_id: Optional[uuid.UUID] = None
    updated_at: datetime

    class Config: from_attributes = True


# ====================== SERVICE ======================

class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_sessions(self, user_id: uuid.UUID) -> list[ChatSession]:
        """Получить все сессии пользователя"""
        result = await self.db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
        )
        return result.scalars().all()

    async def get_session(self, session_id: uuid.UUID, user_id: uuid.UUID) -> Optional[ChatSession]:
        """Получить одну сессию с сообщениями"""
        result = await self.db.execute(
            select(ChatSession)
            .options(selectinload(ChatSession.messages))
            .where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_session(self, user_id: uuid.UUID, title: str = "Новый чат", document_id: Optional[uuid.UUID] = None) -> ChatSession:
        session = ChatSession(user_id=user_id, title=title, document_id=document_id)
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def add_message(self, session_id: uuid.UUID, role: str, content: str) -> ChatMessage:
        msg = ChatMessage(session_id=session_id, role=role, content=content)
        self.db.add(msg)
        await self.db.execute(
            ChatSession.__table__.update()
            .where(ChatSession.id == session_id)
            .values(updated_at=func.now())
        )
        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    async def delete_session(self, session_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return False
        await self.db.delete(session)
        await self.db.commit()
        return True

    async def rename_session(self, session_id: uuid.UUID, user_id: uuid.UUID, title: str) -> Optional[ChatSession]:
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return None
        session.title = title
        await self.db.commit()
        await self.db.refresh(session)
        return session


    async def save_cards(
        self, session_id: uuid.UUID, user_id: uuid.UUID,
        cards: List[Dict], card_index: int = 0,
        card_wrong: int = 0, card_right: int = 0
    ):
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return None
        session.cards = cards
        session.card_index = card_index
        session.card_wrong = card_wrong
        session.card_right = card_right
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def save_roadmap(self, session_id: uuid.UUID, user_id: uuid.UUID, roadmap: List[Dict]):
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return None
        session.roadmap = roadmap
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def save_roadmap(self, session_id: uuid.UUID, user_id: uuid.UUID, roadmap: List[Dict]):
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return None
        session.roadmap = roadmap
        await self.db.commit()
        await self.db.refresh(session)
        return session