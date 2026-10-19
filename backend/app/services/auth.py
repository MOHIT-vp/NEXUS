"""Authentication service — JWT tokens, password hashing, user management."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User, Student, PlacementOfficer

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain-text password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access", "jti": uuid.uuid4().hex})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh", "jti": uuid.uuid4().hex})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def is_revoked(db: AsyncSession, payload: dict) -> bool:
    """True when the token was signed out (server-side revocation list)."""
    from app.models.user import RevokedToken
    jti = payload.get("jti")
    if not jti:
        return False
    return (await db.execute(select(RevokedToken.jti).where(RevokedToken.jti == jti))).first() is not None


async def revoke(db: AsyncSession, payload: Optional[dict]) -> None:
    """Add a token to the revocation list (idempotent)."""
    from app.models.user import RevokedToken
    if not payload or not payload.get("jti") or await is_revoked(db, payload):
        return
    db.add(RevokedToken(jti=payload["jti"], user_id=uuid.UUID(payload["sub"]),
                        expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc)))


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Fetch a user by email."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    """Fetch a user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    password: str,
    full_name: str,
    role: str,
) -> User:
    """Create a new user with role-specific profile."""
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
    )
    db.add(user)
    await db.flush()

    # Create role-specific profile
    if role == "student":
        student = Student(user_id=user.id)
        db.add(student)
    elif role in ("placement_officer", "faculty"):
        officer = PlacementOfficer(user_id=user.id)
        db.add(officer)

    await db.flush()
    return user


class InactiveAccountError(Exception):
    """Correct password, but the account is not active (awaiting approval or deactivated)."""


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    """Authenticate a user by email and password."""
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        raise InactiveAccountError()
    return user
