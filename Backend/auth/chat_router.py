import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from auth.deps import get_current_user
from database.session import get_db
from database.user import User
from database.chat import ChatService, SessionSchema, SessionListItem, MessageSchema, ChatSession
from database.chat import ChatSession, ChatMessage, ChatService, SessionSchema, MessageSchema, SessionListItem
router = APIRouter(prefix="/chat-sessions", tags=["Chat History"])


class CreateSessionRequest(BaseModel):
    title: str = "Новый чат"
    document_id: Optional[uuid.UUID] = None


class AddMessageRequest(BaseModel):
    role: str
    content: str


class RenameSessionRequest(BaseModel):
    title: str

class FlashcardsSaveRequest(BaseModel):
    cards: List[Dict[str, Any]]
    cardIndex: Optional[int] = 0
    cardWrong: Optional[int] = 0
    cardRight: Optional[int] = 0


class RoadmapSaveRequest(BaseModel):
    roadmap: List[Dict[str, Any]]






@router.get("", response_model=list[SessionListItem])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ChatService(db).get_sessions(current_user.id)


@router.post("")
async def create_session(
        session_data: CreateSessionRequest,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    try:
        if session_data.document_id:
            existing_session = await db.scalar(
                select(ChatSession).where(
                    and_(
                        ChatSession.document_id == session_data.document_id,

                    )
                )
            )
            if existing_session:
                return {
                    "id": existing_session.id,
                    "title": existing_session.title,
                    "created_at": existing_session.created_at.isoformat(),
                    "document_id": existing_session.document_id,
                }

        if not session_data.document_id and session_data.title == "Новый чат":
            empty_session = await db.scalar(
                select(ChatSession).where(
                    and_(
                        ChatSession.title == "Новый чат",
                        ChatSession.document_id.is_(None),

                    )
                )
            )
            if empty_session:
                messages_count = await db.scalar(
                    select(func.count()).where(
                        ChatMessage.session_id == empty_session.id
                    )
                )
                if messages_count == 0:
                    return {
                        "id": empty_session.id,
                        "title": empty_session.title,
                        "created_at": empty_session.created_at.isoformat(),
                        "document_id": None,
                    }

        new_session = ChatSession(
            title=session_data.title,
            document_id=session_data.document_id,
            user_id=current_user.id,  # ← важно привязать к пользователю
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)

        return {
            "id": new_session.id,
            "title": new_session.title,
            "created_at": new_session.created_at.isoformat(),
            "document_id": new_session.document_id,
        }

    except HTTPException:
        raise
    except Exception as e:

        print(f"create_session error: {e}")
        import traceback
        traceback.print_exc()
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка создания сессии: {str(e)}")

@router.post("/{session_id}/messages", response_model=MessageSchema, status_code=status.HTTP_201_CREATED)
async def add_chat_message(
    session_id: uuid.UUID,
    body: AddMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify ownership
    session = await ChatService(db).get_session(session_id, current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return await ChatService(db).add_message(session_id, body.role, body.content)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = await ChatService(db).delete_session(session_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
@router.post("/{session_id}/cards")
async def save_flashcards(
    session_id: uuid.UUID,
    body: FlashcardsSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await ChatService(db).save_cards(
        session_id=session_id,
        user_id=current_user.id,
        cards=body.cards,
        card_index=body.cardIndex,
        card_wrong=body.cardWrong,
        card_right=body.cardRight
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "ok"}


@router.post("/{session_id}/roadmap")
async def save_roadmap(
    session_id: uuid.UUID,
    body: RoadmapSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await ChatService(db).save_roadmap(
        session_id=session_id,
        user_id=current_user.id,
        roadmap=body.roadmap
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "ok"}


@router.patch("/{session_id}", response_model=SessionSchema)
async def rename_chat_session(
    session_id: uuid.UUID,
    body: RenameSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await ChatService(db).rename_session(session_id, current_user.id, body.title)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

