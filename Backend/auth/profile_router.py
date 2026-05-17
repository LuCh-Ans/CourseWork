import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from auth.deps import get_current_user
from database.session import get_db
from database.user import User
from database.progress import UserProgress

router = APIRouter(prefix="/profile", tags=["Profile"])


# ──────────────────────────────────────────
# helpers
# ──────────────────────────────────────────

async def _get_or_create_progress(db: AsyncSession, user_id: uuid.UUID) -> UserProgress:
    result = await db.execute(
        select(UserProgress).where(UserProgress.user_id == user_id)
    )
    progress = result.scalar_one_or_none()
    if not progress:
        progress = UserProgress(user_id=user_id)
        db.add(progress)
        await db.flush()
    return progress


def _update_streak_and_days(progress: UserProgress) -> None:
    """Обновляет streak, study_days и activity_map на текущий день."""
    today = datetime.now(timezone.utc).date()
    today_key = today.strftime("%Y-%m-%d")

    activity_map = dict(progress.activity_map or {})

    if today_key not in activity_map:
        # Новый день активности
        activity_map[today_key] = 1
        progress.study_days = len(activity_map)

        last = progress.last_activity_at
        if last:
            yesterday = today - timedelta(days=1)
            if last.date() == yesterday:
                progress.streak_days += 1
            elif last.date() == today:
                pass  # уже считали сегодня — не трогаем
            else:
                progress.streak_days = 1
        else:
            progress.streak_days = 1

        progress.max_streak = max(progress.max_streak or 0, progress.streak_days)
        progress.last_activity_at = datetime.now(timezone.utc)
    else:
        activity_map[today_key] += 1

    progress.activity_map = activity_map


# ──────────────────────────────────────────
# GET /profile/me
# ──────────────────────────────────────────

@router.get("/me")
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    progress = await _get_or_create_progress(db, current_user.id)
    await db.commit()
    await db.refresh(progress)

    return {
        "username": current_user.username or current_user.email or "Пользователь",
        "currentStreak": progress.streak_days or 0,
        "maxStreak": progress.max_streak or 0,
        "studyDays": progress.study_days or 0,
        "chats": progress.chats_count or 0,
        "cardsDone": progress.cards_done or 0,
        "roadmaps": progress.roadmaps_count or 0,
        "totalMinutes": progress.total_minutes or 0,
        "activityMap": progress.activity_map or {},
    }


# ──────────────────────────────────────────
# POST /profile/me/event  — основной endpoint
# ──────────────────────────────────────────

class ActivityEventRequest(BaseModel):
    event: str                    # "message_sent" | "file_uploaded" | "cards_done" | "roadmap_created" | "session_time"
    value: Optional[int] = 1     # для session_time — минуты; для cards_done — количество карточек


@router.post("/me/event")
async def record_event(
    body: ActivityEventRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Фиксирует конкретное действие пользователя и обновляет геймификацию.

    Поддерживаемые события:
      - message_sent    : +1 к chats_count (считаем уникальные сессии на фронте)
      - file_uploaded   : помечает активность дня
      - cards_done      : body.value карточек пройдено → cards_done += value
      - roadmap_created : roadmaps_count += 1
      - session_time    : body.value минут добавляется к total_minutes
    """
    progress = await _get_or_create_progress(db, current_user.id)

    # Всегда обновляем streak/days при любом событии
    _update_streak_and_days(progress)

    event = body.event
    value = body.value or 1

    if event == "message_sent":
        progress.chats_count = (progress.chats_count or 0) + 1
    elif event == "cards_done":
        progress.cards_done = (progress.cards_done or 0) + value
    elif event == "roadmap_created":
        progress.roadmaps_count = (progress.roadmaps_count or 0) + 1
    elif event == "session_time":
        progress.total_minutes = (progress.total_minutes or 0) + value
    # file_uploaded — только streak/days, счётчик документов не храним отдельно

    await db.commit()
    await db.refresh(progress)
    return {"ok": True}


# ──────────────────────────────────────────
# POST /profile/me/activity  — обратная совместимость
# ──────────────────────────────────────────

@router.post("/me/activity")
async def record_activity(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Устаревший endpoint — обновляет только streak/days."""
    progress = await _get_or_create_progress(db, current_user.id)
    _update_streak_and_days(progress)
    await db.commit()
    return {"ok": True}