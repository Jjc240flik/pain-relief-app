"""
Authentication service — JWT-based with password hashing (SHA-256 + salt).

Provides:
  - Password hashing (SHA-256 with random salt)
  - JWT token creation & verification
  - FastAPI dependency for protected routes
  - Two roles: owner (full access), project_manager (dashboard + limited admin)
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, async_session

logger = logging.getLogger(__name__)

# ── Config ──
SECRET_KEY = "tlq-andon-secret-change-in-production-2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours


# ── User ORM Model ──
class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    username: Mapped[str] = mapped_column(unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(nullable=False)
    display_name: Mapped[str] = mapped_column(default="")
    role: Mapped[str] = mapped_column(default="project_manager")  # owner | project_manager
    is_active: Mapped[bool] = mapped_column(default=True)


# ── Password helpers (SHA-256 + random salt) ──

def hash_password(password: str) -> str:
    """Hash a password with a random salt. Format: salt$hash"""
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a salt$hash string."""
    try:
        salt, h = hashed.split("$", 1)
        return hashlib.sha256((salt + plain).encode()).hexdigest() == h
    except (ValueError, AttributeError):
        return False


# ── JWT helpers ──
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# ── Session storage (cookie-based JWT) ──
TOKEN_COOKIE_NAME = "andon_token"


def set_token_cookie(response, token: str):
    response.set_cookie(
        key=TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False,
    )


def delete_token_cookie(response):
    response.delete_cookie(TOKEN_COOKIE_NAME)


# ── FastAPI dependencies ──

async def get_current_user(request: Request) -> dict | None:
    """Extract the current user from the JWT cookie. Returns None if not authenticated."""
    token = request.cookies.get(TOKEN_COOKIE_NAME)
    if not token:
        return None
    payload = decode_access_token(token)
    if payload is None:
        return None
    return {
        "id": payload.get("sub"),
        "username": payload.get("username", ""),
        "role": payload.get("role", ""),
        "display_name": payload.get("display_name", ""),
    }


async def require_owner(user: dict = Depends(get_current_user)):
    """Require owner role. Redirects to login if not authenticated."""
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})
    if user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    return user


async def require_admin(user: dict = Depends(get_current_user)):
    """Require any authenticated user."""
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})
    return user


async def optional_user(user: dict = Depends(get_current_user)):
    """Return user if authenticated, None otherwise."""
    return user


# ── User CRUD ──

async def get_user_by_username(username: str) -> User | None:
    async with async_session() as session:
        stmt = select(User).where(User.username == username, User.is_active == True)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def create_user(username: str, password: str, display_name: str = "", role: str = "project_manager") -> User:
    """Create a new user. Returns the User object."""
    async with async_session() as session:
        user = User(
            username=username,
            hashed_password=hash_password(password),
            display_name=display_name or username,
            role=role,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info("Created user: %s (role=%s)", username, role)
        return user
