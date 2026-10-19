"""
Lab 14 (Capstone): Admin API.

System management endpoints — admin role only: system stats, Placement Cell
accounts (create / activate / deactivate) and the audit log. The admin manages
the system; approving student plans stays with the Placement Cell.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.models.user import User
from app.models.workflow import AuditLog, WorkflowRun, ApprovalDecision, Version
from app.schemas.auth import UserRegister
from app.services import auth as auth_service
from app.core.domains.registry import get_all_domains, get_domain_config

router = APIRouter(prefix="/admin", tags=["Admin"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DomainSummary(BaseModel):
    family_id: str
    name: str
    description: str
    required_skills: List[str]
    weights: Dict[str, float]


class SystemStats(BaseModel):
    total_workflow_runs: int
    pending_review: int
    validation_failed: int = 0
    users_by_role: Dict[str, int] = {}
    approved: int
    rejected: int
    published_versions: int


# ---------------------------------------------------------------------------
# Domain Config Endpoints
# ---------------------------------------------------------------------------

@router.get("/domains", response_model=List[DomainSummary])
async def list_all_domains(
    current_user: User = Depends(require_role("admin", "placement_officer")),
):
    """
    List all registered domain specialist configurations.
    Accessible to admins and placement officers for reference.
    """
    configs = get_all_domains()
    return [
        DomainSummary(
            family_id=c.family_id,
            name=c.name,
            description=c.description,
            required_skills=c.taxonomy.required_skills,
            weights={
                "skill_coverage": c.weights.skill_coverage,
                "coding_performance": c.weights.coding_performance,
                "project_relevance": c.weights.project_relevance,
                "interview_performance": c.weights.interview_performance,
                "eligibility": c.weights.eligibility,
            },
        )
        for c in configs
    ]


@router.get("/domains/{family_id}", response_model=Dict[str, Any])
async def get_domain_detail(
    family_id: str,
    current_user: User = Depends(require_role("admin", "placement_officer")),
):
    """
    Get the full domain configuration for a specific role family.
    Includes taxonomy, question bank, and scoring weights.
    """
    config = get_domain_config(family_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain '{family_id}' not found. Available: software, analytics, core, higher_studies",
        )
    return config.model_dump()


# ---------------------------------------------------------------------------
# System Stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=SystemStats)
async def get_system_stats(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    System-wide statistics for the admin panel.
    Provides counts of pipeline runs, approval rates, and published plans.
    """
    # Total workflow runs
    total_result = await db.execute(select(func.count(WorkflowRun.id)))
    total_runs = total_result.scalar() or 0

    # By status
    pending_result = await db.execute(
        select(func.count(WorkflowRun.id)).where(WorkflowRun.status == "pending_review")
    )
    pending = pending_result.scalar() or 0
    failed = (await db.execute(
        select(func.count(WorkflowRun.id)).where(WorkflowRun.status == "validation_failed"))).scalar() or 0
    by_role = dict((await db.execute(select(User.role, func.count(User.id)).group_by(User.role))).all())

    approved_result = await db.execute(
        select(func.count(ApprovalDecision.id)).where(ApprovalDecision.decision == "approved")
    )
    approved = approved_result.scalar() or 0

    rejected_result = await db.execute(
        select(func.count(ApprovalDecision.id)).where(ApprovalDecision.decision == "rejected")
    )
    rejected = rejected_result.scalar() or 0

    published_result = await db.execute(
        select(func.count(Version.id)).where(Version.status == "published")
    )
    published = published_result.scalar() or 0

    return SystemStats(
        total_workflow_runs=total_runs,
        pending_review=pending,
        validation_failed=failed,
        users_by_role=by_role,
        approved=approved,
        rejected=rejected,
        published_versions=published,
    )


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

STAFF_ROLES = ("placement_officer", "admin")


class AccountOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: Optional[datetime] = None


class AccountCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field("placement_officer", pattern="^(placement_officer|admin)$")

    _strength = field_validator("password")(UserRegister.password_strength.__func__)


class AccountUpdate(BaseModel):
    is_active: bool


@router.get("/users", response_model=List[AccountOut])
async def list_accounts(
    role: Optional[str] = Query(None),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    q = select(User).order_by(User.role, User.created_at.desc())
    if role:
        q = q.where(User.role == role)
    return (await db.execute(q)).scalars().all()


@router.post("/users", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
async def create_staff_account(
    body: AccountCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a Placement Cell (or admin) account. Students register themselves."""
    if await auth_service.get_user_by_email(db, body.email):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = await auth_service.create_user(db, email=body.email, password=body.password,
                                          full_name=body.full_name.strip(), role=body.role)
    db.add(AuditLog(actor_id=current_user.id, actor_type="admin", action="ACCOUNT_CREATED", entity_type="user",
                    entity_id=user.id, correlation_id=uuid.uuid4(), details={"email": body.email, "role": body.role}))
    await db.commit()
    return user


@router.patch("/users/{user_id}", response_model=AccountOut)
async def set_account_active(
    user_id: uuid.UUID,
    body: AccountUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Activate or deactivate an account. A deactivated user's tokens stop working at once."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    if user.id == current_user.id and not body.is_active:
        raise HTTPException(status_code=409, detail="You can't deactivate your own account.")
    user.is_active = body.is_active
    db.add(AuditLog(actor_id=current_user.id, actor_type="admin",
                    action="ACCOUNT_ACTIVATED" if body.is_active else "ACCOUNT_DEACTIVATED",
                    entity_type="user", entity_id=user.id, correlation_id=uuid.uuid4(),
                    details={"email": user.email, "role": user.role}))
    await db.commit()
    return user


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

@router.get("/audit", response_model=List[Dict[str, Any]])
async def recent_audit_log(
    limit: int = Query(100, ge=1, le=500),
    action: Optional[str] = Query(None),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    q = (select(AuditLog, User.email).outerjoin(User, User.id == AuditLog.actor_id)
         .order_by(AuditLog.timestamp.desc()).limit(limit))
    if action:
        q = q.where(AuditLog.action == action)
    return [{
        "id": str(a.id), "timestamp": a.timestamp.isoformat() if a.timestamp else None,
        "actor": email or a.actor_type, "actor_type": a.actor_type, "agent": a.agent_name,
        "action": a.action, "entity_type": a.entity_type,
        "entity_id": str(a.entity_id) if a.entity_id else None,
        "workflow_run_id": str(a.workflow_run_id) if a.workflow_run_id else None,
        "details": a.details or {},
    } for a, email in (await db.execute(q)).all()]
