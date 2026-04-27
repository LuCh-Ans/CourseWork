from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from auth.auth_service import AuthService
from auth.deps import SESSION_COOKIE_NAME
from config import settings
from database.session import get_db


class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: object
    email: str
    username: str


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await AuthService(db).register(body.email, body.username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return UserResponse(id=user.id, email=user.email, username=user.username)


@router.post("/login", response_model=UserResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        user, session_id = await AuthService(db).login(body.email, body.password)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=settings.SESSION_EXPIRE_SECONDS,
    )
    return UserResponse(id=user.id, email=user.email, username=user.username)


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
):
    if session_id:
        await AuthService(db).logout(session_id)
    response.delete_cookie(SESSION_COOKIE_NAME)