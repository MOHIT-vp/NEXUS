"""
Lab 12: Versioning & Rollback API

Creates immutable version snapshots on approval and allows one-click rollback.
RBAC: version creation by officers only; rollback by officers and admins.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.models.user import User
from app.models.workflow import Version, WorkflowRun, AuditLog

async def _assert_own_or_staff(db: AsyncSession, user: User, student_id: uuid.UUID) -> None:
    if user.role != "student":
        return
    from app.models.user import Student
    own = (await db.execute(select(Student.id).where(Student.user_id == user.id))).scalar_one_or_none()
    if own != student_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")


router = APIRouter(prefix="/versions", tags=["Versions"])


async def _rollback_problems(db: AsyncSession, target: Version) -> List[str]:
    """Why a stored version may not be re-published now (empty list = OK)."""
    from app.agents.validation_agent import validation_agent_node
    from app.models.user import Consent
    from app.services.consent import consent_status, is_granted, missing_required

    snap = target.snapshot or {}
    problems: List[str] = []
    consents = consent_status((await db.execute(select(Consent).where(Consent.student_id == target.student_id))).scalars().all())
    if missing_required(consents):
        problems.append("the student has withdrawn consent to process their resume")
    used = {s.get("source") for s in (snap.get("coding_analytics") or {}).get("sources", []) if s.get("status") == "ok"}
    for source in sorted(used & {"github", "leetcode"}):
        if not is_granted(consents, source):
            problems.append(f"it uses {source} data the student no longer shares")
    academic = (snap.get("student_context") or {}).get("academic") or {}
    if academic.get("cgpa") is not None and not is_granted(consents, "academic_records"):
        problems.append("it uses academic records the student no longer shares")
    try:
        report = validation_agent_node({**snap, "consent_validated": not missing_required(consents)})["validation_report"]
        failed = [c["name"] for c in report.get("checks", []) if not c["passed"] and c["severity"] == "error"]
    except Exception as exc:  # a snapshot that cannot be validated is not restored
        failed = [f"validation could not run ({exc.__class__.__name__})"]
    if failed:
        problems.append("required checks now fail: " + ", ".join(failed))
    return problems


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class VersionCreateRequest(BaseModel):
    workflow_run_id: uuid.UUID
    entity_type: str = "readiness_plan"
    snapshot: Dict[str, Any]           # The full readiness plan content to version


class VersionResponse(BaseModel):
    version_id: uuid.UUID
    student_id: uuid.UUID
    entity_type: str
    version_number: int
    status: str
    workflow_run_id: Optional[uuid.UUID]
    published_at: Optional[str]
    created_at: str


class RollbackResponse(BaseModel):
    message: str
    active_version_id: uuid.UUID
    active_version_number: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/", response_model=VersionResponse, status_code=status.HTTP_201_CREATED)
async def create_version(
    request: VersionCreateRequest,
    current_user: User = Depends(require_role("placement_officer")),
    db: AsyncSession = Depends(get_db),
):
    """
    Create an immutable version snapshot of an approved readiness plan.
    Only triggered after an officer approval decision.
    Automatically assigns the next sequential version number.
    """
    # Verify the workflow run exists
    run_result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == request.workflow_run_id))
    run = run_result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found")

    # Must be approved before versioning
    if run.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot version a workflow run with status '{run.status}'. Must be 'approved'.",
        )

    # Calculate next version number for this student + entity_type
    count_result = await db.execute(
        select(func.count(Version.id)).where(
            Version.student_id == run.student_id,
            Version.entity_type == request.entity_type,
        )
    )
    next_version_number = (count_result.scalar() or 0) + 1

    version = Version(
        student_id=run.student_id,
        entity_type=request.entity_type,
        version_number=next_version_number,
        status="published",
        snapshot=run.result_snapshot,   # always the reviewed draft, never client-supplied content
        workflow_run_id=request.workflow_run_id,
        approved_by=current_user.id,
        published_at=datetime.now(timezone.utc),
    )
    db.add(version)

    # Audit log
    audit = AuditLog(
        actor_id=current_user.id,
        actor_type="placement_officer",
        workflow_run_id=request.workflow_run_id,
        action="version_created",
        entity_type="version",
        version=next_version_number,
        correlation_id=uuid.uuid4(),
        details={"entity_type": request.entity_type, "version_number": next_version_number},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(version)

    return VersionResponse(
        version_id=version.id,
        student_id=version.student_id,
        entity_type=version.entity_type,
        version_number=version.version_number,
        status=version.status,
        workflow_run_id=version.workflow_run_id,
        published_at=version.published_at.isoformat() if version.published_at else None,
        created_at=version.created_at.isoformat(),
    )


@router.get("/student/{student_id}", response_model=List[VersionResponse])
async def list_student_versions(
    student_id: uuid.UUID,
    entity_type: Optional[str] = None,
    current_user: User = Depends(require_role("placement_officer", "admin", "student")),
    db: AsyncSession = Depends(get_db),
):
    """List all versions for a student, optionally filtered by entity_type (students: own only)."""
    await _assert_own_or_staff(db, current_user, student_id)
    query = select(Version).where(Version.student_id == student_id)
    if entity_type:
        query = query.where(Version.entity_type == entity_type)
    query = query.order_by(Version.version_number.desc())

    result = await db.execute(query)
    versions = result.scalars().all()

    return [
        VersionResponse(
            version_id=v.id,
            student_id=v.student_id,
            entity_type=v.entity_type,
            version_number=v.version_number,
            status=v.status,
            workflow_run_id=v.workflow_run_id,
            published_at=v.published_at.isoformat() if v.published_at else None,
            created_at=v.created_at.isoformat(),
        )
        for v in versions
    ]


@router.get("/{version_id}", response_model=Dict[str, Any])
async def get_version_snapshot(
    version_id: uuid.UUID,
    current_user: User = Depends(require_role("placement_officer", "admin", "student")),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the full snapshot content of a specific version.
    This is the immutable record of what was approved at that point in time.
    """
    result = await db.execute(select(Version).where(Version.id == version_id))
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    await _assert_own_or_staff(db, current_user, version.student_id)

    return {
        "version_id": str(version.id),
        "student_id": str(version.student_id),
        "entity_type": version.entity_type,
        "version_number": version.version_number,
        "status": version.status,
        "published_at": version.published_at.isoformat() if version.published_at else None,
        "snapshot": version.snapshot,
    }


@router.post("/{version_id}/rollback", response_model=RollbackResponse)
async def rollback_to_version(
    version_id: uuid.UUID,
    current_user: User = Depends(require_role("placement_officer")),
    db: AsyncSession = Depends(get_db),
):
    """
    One-click rollback: mark a previous version as 'active' and archive the current one.
    Creates an audit log entry for the rollback operation.
    """
    result = await db.execute(select(Version).where(Version.id == version_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    if target.status == "rolled_back":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot roll back to a version that was itself rolled back.",
        )

    # Re-check before restoring: the old plan must still pass the required checks,
    # and must not rely on data the student has since stopped sharing.
    problems = await _rollback_problems(db, target)
    if problems:
        db.add(AuditLog(actor_id=current_user.id, actor_type="placement_officer", action="version_rollback_refused",
                        entity_type="version", entity_id=version_id, version=target.version_number,
                        correlation_id=uuid.uuid4(), details={"problems": problems, "student_id": str(target.student_id)}))
        await db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"message": "This version can't be restored: " + "; ".join(problems), "problems": problems})

    # Archive all other published versions for this student + entity_type
    all_versions_result = await db.execute(
        select(Version).where(
            Version.student_id == target.student_id,
            Version.entity_type == target.entity_type,
            Version.id != version_id,
            Version.status == "published",
        )
    )
    for v in all_versions_result.scalars().all():
        v.status = "archived"

    # Restore the target
    target.status = "published"

    # Audit
    audit = AuditLog(
        actor_id=current_user.id,
        actor_type="placement_officer",
        action="version_rollback",
        entity_type="version",
        entity_id=version_id,
        version=target.version_number,
        correlation_id=uuid.uuid4(),
        details={
            "rolled_back_to_version": target.version_number,
            "revalidated": True,
            "entity_type": target.entity_type,
            "student_id": str(target.student_id),
        },
    )
    db.add(audit)
    await db.commit()

    return RollbackResponse(
        message=f"Successfully rolled back to version {target.version_number}.",
        active_version_id=target.id,
        active_version_number=target.version_number,
    )
