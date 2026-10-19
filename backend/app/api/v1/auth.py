"""Authentication API router."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    TokenRefresh, TokenResponse, UserLogin, UserRegister, UserResponse,
)
from app.services import auth as auth_service
from typing import Optional

import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.workflow import AuditLog

from app.api.deps import get_current_user, oauth2_scheme

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user and return tokens."""
    existing_user = await auth_service.get_user_by_email(db, user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    user = await auth_service.create_user(
        db=db,
        email=user_in.email,
        password=user_in.password,
        full_name=user_in.full_name,
        role="student",
    )

    access_token = auth_service.create_access_token({"sub": str(user.id), "role": user.role})
    refresh_token = auth_service.create_refresh_token({"sub": str(user.id), "role": user.role})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 1800,  # 30 mins
        "user": user,
    }


class PlacementCellSignup(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)

    _strength = field_validator("password")(UserRegister.password_strength.__func__)


@router.post("/register-placement-cell", status_code=status.HTTP_202_ACCEPTED)
async def register_placement_cell(body: PlacementCellSignup, db: AsyncSession = Depends(get_db)):
    """
    Request a Placement Cell account. It is created INACTIVE: it cannot sign in or
    approve anything until an administrator activates it on the Admin page.
    """
    if await auth_service.get_user_by_email(db, body.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")
    user = await auth_service.create_user(db=db, email=body.email, password=body.password,
                                          full_name=body.full_name.strip(), role="placement_officer")
    user.is_active = False
    db.add(AuditLog(actor_id=user.id, actor_type="placement_officer", action="PLACEMENT_CELL_SIGNUP_PENDING",
                    entity_type="user", entity_id=user.id, correlation_id=uuid.uuid4(), details={"email": body.email}))
    await db.commit()
    return {"message": "Request received. An administrator must approve your Placement Cell account before you can sign in."}


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """OAuth2 compatible token login, getting an access token for future requests."""
    try:
        user = await auth_service.authenticate_user(db, form_data.username, form_data.password)
    except auth_service.InactiveAccountError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account isn't active yet. Placement Cell accounts need an administrator's approval before first sign-in.",
        )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth_service.create_access_token({"sub": str(user.id), "role": user.role})
    refresh_token = auth_service.create_refresh_token({"sub": str(user.id), "role": user.role})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 1800,
        "user": user,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(token_in: TokenRefresh, db: AsyncSession = Depends(get_db)):
    """Refresh an access token using a refresh token."""
    payload = auth_service.decode_token(token_in.refresh_token)
    
    if not payload or payload.get("type") != "refresh" or await auth_service.is_revoked(db, payload):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    import uuid
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = await auth_service.get_user_by_id(db, uuid.UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Rotation: each refresh token works once; the client gets a new one
    await auth_service.revoke(db, payload)
    await db.commit()
    access_token = auth_service.create_access_token({"sub": str(user.id), "role": user.role})
    refresh_token = auth_service.create_refresh_token({"sub": str(user.id), "role": user.role})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 1800,
        "user": user,
    }


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: Optional[LogoutRequest] = None,
    token: Optional[str] = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sign out on the server: this access token (and the refresh token, if sent) stop working."""
    await auth_service.revoke(db, auth_service.decode_token(token))
    if body and body.refresh_token:
        refresh = auth_service.decode_token(body.refresh_token)
        if refresh and refresh.get("sub") == str(current_user.id):
            await auth_service.revoke(db, refresh)
    await db.commit()
    return None


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user's profile."""
    return current_user
