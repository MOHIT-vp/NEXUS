"""
Lab 12: Consent Management API

Students grant and revoke explicit per-type consent.
Consent is a hard prerequisite for the pipeline (enforced by consent_validation node).

Consent types (one per data source):
- resume_processing    : analyse the uploaded resume (required)
- github               : read the public GitHub profile for the handle given
- leetcode             : read the public LeetCode profile for the handle given
- academic_records     : use the CGPA entered for eligibility checks
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_student, get_current_user, get_db
from app.models.user import Student, User
from app.models.workflow import AuditLog
from app.models.user import Consent

router = APIRouter(prefix="/consents", tags=["Consents"])

from app.services.consent import CONSENT_SOURCES

VALID_CONSENT_TYPES = set(CONSENT_SOURCES)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ConsentGrantRequest(BaseModel):
    consent_type: str


class ConsentStatusResponse(BaseModel):
    consent_type: str
    granted: bool
    granted_at: Optional[str]
    revoked_at: Optional[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/me", response_model=List[ConsentStatusResponse])
async def get_my_consents(
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Get all consent records for the current student."""
    result = await db.execute(
        select(Consent).where(Consent.student_id == current_student.id)
    )
    consents = result.scalars().all()

    # Build full status for all consent types (including ones not yet recorded)
    consent_map = {c.consent_type: c for c in consents}
    return [
        ConsentStatusResponse(
            consent_type=ct,
            granted=consent_map[ct].granted if ct in consent_map else False,
            granted_at=consent_map[ct].granted_at.isoformat() if ct in consent_map and consent_map[ct].granted_at else None,
            revoked_at=consent_map[ct].revoked_at.isoformat() if ct in consent_map and consent_map[ct].revoked_at else None,
        )
        for ct in VALID_CONSENT_TYPES
    ]


@router.post("/me/grant", response_model=ConsentStatusResponse, status_code=status.HTTP_200_OK)
async def grant_consent(
    request_body: ConsentGrantRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    Grant explicit consent for a specific data processing type.
    Idempotent: granting an already-granted consent is a no-op.
    """
    if request_body.consent_type not in VALID_CONSENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid consent_type '{request_body.consent_type}'. "
                   f"Valid types: {sorted(VALID_CONSENT_TYPES)}",
        )

    result = await db.execute(
        select(Consent).where(
            Consent.student_id == current_student.id,
            Consent.consent_type == request_body.consent_type,
        )
    )
    consent = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    client_ip = http_request.client.host if http_request.client else None

    if consent is None:
        consent = Consent(
            student_id=current_student.id,
            consent_type=request_body.consent_type,
            granted=True,
            granted_at=now,
            ip_address=client_ip,
        )
        db.add(consent)
    elif not consent.granted:
        consent.granted = True
        consent.granted_at = now
        consent.revoked_at = None
        consent.ip_address = client_ip

    # Audit log
    audit = AuditLog(
        actor_id=current_user.id,
        actor_type="student",
        action="consent_granted",
        entity_type="consent",
        correlation_id=uuid.uuid4(),
        details={"consent_type": request_body.consent_type, "ip": client_ip},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(consent)

    return ConsentStatusResponse(
        consent_type=consent.consent_type,
        granted=consent.granted,
        granted_at=consent.granted_at.isoformat() if consent.granted_at else None,
        revoked_at=consent.revoked_at.isoformat() if consent.revoked_at else None,
    )


@router.post("/me/revoke", response_model=ConsentStatusResponse, status_code=status.HTTP_200_OK)
async def revoke_consent(
    request_body: ConsentGrantRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke a previously granted consent.
    Revoking consent stops future pipeline runs that require that consent type.
    Historical data already processed is retained per data_retention policy.
    """
    if request_body.consent_type not in VALID_CONSENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid consent_type '{request_body.consent_type}'.",
        )

    result = await db.execute(
        select(Consent).where(
            Consent.student_id == current_student.id,
            Consent.consent_type == request_body.consent_type,
        )
    )
    consent = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if consent is None or not consent.granted:
        # Nothing to revoke — return current (non-granted) state
        return ConsentStatusResponse(
            consent_type=request_body.consent_type,
            granted=False,
            granted_at=None,
            revoked_at=None,
        )

    consent.granted = False
    consent.revoked_at = now

    audit = AuditLog(
        actor_id=current_user.id,
        actor_type="student",
        action="consent_revoked",
        entity_type="consent",
        correlation_id=uuid.uuid4(),
        details={"consent_type": request_body.consent_type},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(consent)

    return ConsentStatusResponse(
        consent_type=consent.consent_type,
        granted=consent.granted,
        granted_at=consent.granted_at.isoformat() if consent.granted_at else None,
        revoked_at=consent.revoked_at.isoformat() if consent.revoked_at else None,
    )
