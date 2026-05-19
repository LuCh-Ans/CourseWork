import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.user import User
from database.user_session import UserSession


def _hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    import bcrypt
    return bcrypt.checkpw(password.encode(), hashed.encode())


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, email: str, username: str, password: str) -> User:

        existing = await self.db.execute(
            select(User).where((User.email == email) | (User.username == username))
        )
        if existing.scalar_one_or_none():
            raise ValueError("Email or username already taken.")

        user = User(
            email=email,
            username=username,
            hashed_password=_hash_password(password),
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def login(self, email: str, password: str) -> tuple[User, str]:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user or not _verify_password(password, user.hashed_password):
            raise PermissionError("Invalid email or password.")

        session_id = uuid.uuid4().hex
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.SESSION_EXPIRE_SECONDS)

        session = UserSession(id=session_id, user_id=user.id, expires_at=expires_at)
        self.db.add(session)
        await self.db.commit()
        return user, session_id

    async def logout(self, session_id: str) -> None:
        await self.db.execute(delete(UserSession).where(UserSession.id == session_id))
        await self.db.commit()

    async def get_user_by_session(self, session_id: str) -> User | None:
        result = await self.db.execute(
            select(UserSession).where(UserSession.id == session_id)
        )
        session = result.scalar_one_or_none()

        if not session:
            return None
        if session.expires_at < datetime.now(timezone.utc):
            await self.logout(session_id)
            return None

        result = await self.db.execute(select(User).where(User.id == session.user_id))
        return result.scalar_one_or_none()