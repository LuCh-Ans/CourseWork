import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from auth.deps import get_current_user
from database.session import get_db
from database.user import User
from database.progress import UserProgress

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("")
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UserProgress).where(UserProgress.user_id == current_user.id)
    )
    progress = result.scalar_one_or_none()

    if not progress:
        progress = UserProgress(user_id=current_user.id)
        db.add(progress)
        await db.commit()
        await db.refresh(progress)

    return {
        "username": current_user.email or current_user.username or "Пользователь",  # ← исправлено
        "currentStreak": progress.streak_days or 0,
        "maxStreak": progress.max_streak or 0,
        "studyDays": progress.study_days or 0,
        "chats": progress.chats_count or 0,
        "cardsDone": progress.cards_done or 0,
        "roadmaps": progress.roadmaps_count or 0,
        "totalMinutes": progress.total_minutes or 0,
        "activityMap": progress.activity_map or {},
    }


@router.post("/activity")
async def record_activity(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Вызывается при действиях пользователя"""
    result = await db.execute(
        select(UserProgress).where(UserProgress.user_id == current_user.id)
    )
    progress = result.scalar_one_or_none()

    if not progress:
        progress = UserProgress(user_id=current_user.id)
        db.add(progress)

    today = datetime.now(timezone.utc).date()
    today_key = today.strftime("%Y-%m-%d")

    activity_map = dict(progress.activity_map or {})

    if today_key not in activity_map:
        activity_map[today_key] = 1
        progress.study_days = len(activity_map)

        # Обновление streak
        last = progress.last_activity_at
        if last:
            yesterday = today - timezone.timedelta(days=1)
            if last.date() == yesterday:
                progress.streak_days += 1
            else:
                progress.streak_days = 1
        else:
            progress.streak_days = 1

        progress.max_streak = max(progress.max_streak, progress.streak_days)
        progress.last_activity_at = datetime.now(timezone.utc)
    else:
        activity_map[today_key] += 1

    progress.activity_map = activity_map
    await db.commit()
    await db.refresh(progress)
    return {"ok": True}