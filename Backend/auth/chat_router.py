import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from auth.deps import get_current_user
from database.session import get_db
from database.user import User
from database.chat import ChatService, SessionSchema, SessionListItem, MessageSchema

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


@router.post("", response_model=SessionSchema, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await ChatService(db).create_session(
        current_user.id, body.title, body.document_id
    )
    # Важно: не загружаем messages при создании
    return await ChatService(db).get_session(session.id, current_user.id)


@router.get("/{session_id}", response_model=SessionSchema)
async def get_chat_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await ChatService(db).get_session(session_id, current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


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

