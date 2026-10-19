"""API dependencies — authentication, authorization, database session."""
import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, Student
from app.services.auth import decode_token, is_revoked

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current user from the JWT token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    if await is_revoked(db, payload):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signed out — please sign in again")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return user


async def get_current_student(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Student:
    """Get the Student record for the current user (student role only)."""
    if user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student access required")

    result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
    return student


def require_role(*roles: str):
    """Dependency factory: require the user to have one of the specified roles."""
    async def _check_role(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' does not have access. Required: {', '.join(roles)}",
            )
        return user
    return _check_role


def scope_student_access(user: User, target_student_id: uuid.UUID, student: Optional[Student] = None):
    """Enforce per-student data isolation. Students can only access their own data."""
    if user.role == "student":
        if student and student.id != target_student_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: not your data")
        # For cases where we just have user + student_id but no Student object loaded yet
        # The caller should verify student.user_id == user.id
    # Officers, faculty, and admins can access any student's data


async def can_view_run(db: AsyncSession, user: User, run) -> bool:
    """A student may view only their own runs; the Placement Cell (and admin) may view any run."""
    if user.role in ("placement_officer", "admin"):
        return True
    if user.role == "student":
        result = await db.execute(select(Student.id).where(Student.user_id == user.id))
        return result.scalar_one_or_none() == run.student_id
    return False
