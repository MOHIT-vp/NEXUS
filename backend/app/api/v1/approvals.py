"""
Lab 12: Approval Workflow API

Officer-only endpoints for the review → approve/reject/edit → publish flow.
RBAC: only users with role 'placement_officer' or 'admin' can act on approvals.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.models.user import User
from app.models.workflow import ApprovalDecision, WorkflowRun, AuditLog

router = APIRouter(prefix="/approvals", tags=["Approvals"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ApprovalRequest(BaseModel):
    decision: str               # "approved" | "rejected" | "changes_requested"
    comments: Optional[str] = None
    edits: Optional[Dict[str, Any]] = None  # Officer-applied edits to the draft


class ApprovalResponse(BaseModel):
    approval_id: uuid.UUID
    workflow_run_id: uuid.UUID
    decision: str
    comments: Optional[str]
    reviewed_by: str
    reviewed_at: str


class ApprovalQueueItem(BaseModel):
    workflow_run_id: uuid.UUID
    student_id: uuid.UUID
    status: str
    current_step: str
    created_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/queue", response_model=List[ApprovalQueueItem])
async def get_approval_queue(
    current_user: User = Depends(require_role("placement_officer", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all workflow runs awaiting officer approval.
    Accessible only to placement_officer and admin roles.
    """
    result = await db.execute(
        select(WorkflowRun).where(WorkflowRun.status == "completed").order_by(WorkflowRun.created_at.desc())
    )
    runs = result.scalars().all()

    return [
        ApprovalQueueItem(
            workflow_run_id=run.id,
            student_id=run.student_id,
            status=run.status,
            current_step=run.current_step or "unknown",
            created_at=run.created_at.isoformat() if run.created_at else "",
        )
        for run in runs
    ]


@router.post("/{workflow_run_id}", response_model=ApprovalResponse, status_code=status.HTTP_201_CREATED)
async def submit_approval(
    workflow_run_id: uuid.UUID,
    request: ApprovalRequest,
    current_user: User = Depends(require_role("placement_officer", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit an approval decision (approve / reject / request changes).
    Only placement officers and admins may call this.

    - approved         → workflow publishes; triggers Version creation
    - rejected         → workflow marked rejected; student notified
    - changes_requested → workflow returned for amendments
    """
    # Validate decision value
    valid_decisions = {"approved", "rejected", "changes_requested"}
    if request.decision not in valid_decisions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid decision '{request.decision}'. Must be one of: {valid_decisions}",
        )

    # Verify the workflow run exists
    result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found")

    # Prevent duplicate approvals on a run that is already decided
    existing = await db.execute(
        select(ApprovalDecision).where(
            ApprovalDecision.workflow_run_id == workflow_run_id,
            ApprovalDecision.decision.in_(["approved", "rejected"])
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This workflow run already has a final approval decision.",
        )

    # Record the decision
    approval = ApprovalDecision(
        workflow_run_id=workflow_run_id,
        reviewer_id=current_user.id,
        decision=request.decision,
        comments=request.comments,
        edits=request.edits,
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add(approval)

    # Update workflow run status
    run.status = request.decision  # "approved" / "rejected" / "changes_requested"

    # Write audit log entry
    audit = AuditLog(
        actor_id=current_user.id,
        actor_type="placement_officer",
        workflow_run_id=workflow_run_id,
        action="approval_decision",
        entity_type="workflow_run",
        entity_id=workflow_run_id,
        decision=request.decision,
        approval_decision=request.decision,
        correlation_id=uuid.uuid4(),
        details={"comments": request.comments, "edits_applied": bool(request.edits)},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(approval)

    return ApprovalResponse(
        approval_id=approval.id,
        workflow_run_id=workflow_run_id,
        decision=approval.decision,
        comments=approval.comments,
        reviewed_by=current_user.full_name,
        reviewed_at=approval.reviewed_at.isoformat(),
    )


@router.get("/{workflow_run_id}", response_model=List[ApprovalResponse])
async def get_approval_history(
    workflow_run_id: uuid.UUID,
    current_user: User = Depends(require_role("placement_officer", "admin", "student")),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all approval decisions for a specific workflow run.
    Students can read their own approval history; officers can read all.
    """
    result = await db.execute(
        select(ApprovalDecision, User)
        .join(User, ApprovalDecision.reviewer_id == User.id)
        .where(ApprovalDecision.workflow_run_id == workflow_run_id)
        .order_by(ApprovalDecision.reviewed_at.asc())
    )
    rows = result.all()

    return [
        ApprovalResponse(
            approval_id=decision.id,
            workflow_run_id=workflow_run_id,
            decision=decision.decision,
            comments=decision.comments,
            reviewed_by=reviewer.full_name,
            reviewed_at=decision.reviewed_at.isoformat(),
        )
        for decision, reviewer in rows
    ]


# ---------------------------------------------------------------------------
# MVP Unauthenticated Endpoints (for frontend without login)
# 
# SECURITY WARNING: These endpoints are currently unauthenticated to facilitate
# frontend testing and demonstration of the Officer Workflow. 
# 
# FUTURE REQUIREMENT: Before production, these endpoints MUST be secured
# using `Depends(require_role("placement_officer"))` to ensure that students
# cannot bypass human approval by calling these endpoints directly.
# The conceptual separation between Student and Officer actions is maintained
# structurally, but proper JWT validation is required for true security.
# ---------------------------------------------------------------------------

@router.get("/queue/open")
async def get_open_approval_queue(
    db: AsyncSession = Depends(get_db),
):
    """
    MVP: Get all workflow runs awaiting officer review (no auth required).
    Returns pending_review and completed runs for the officer console.
    
    SECURITY REQUIREMENT: To be locked down with `require_role("placement_officer")`
    in Phase 3 / Production.
    """
    result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.status.in_(["pending_review", "completed"]))
        .order_by(WorkflowRun.created_at.desc())
        .limit(50)
    )
    runs = result.scalars().all()

    # Get recent decisions
    decisions_result = await db.execute(
        select(ApprovalDecision)
        .order_by(ApprovalDecision.reviewed_at.desc())
        .limit(10)
    )
    recent_decisions = decisions_result.scalars().all()

    # Get counts
    from sqlalchemy import func
    approved_count_result = await db.execute(
        select(func.count(ApprovalDecision.id)).where(ApprovalDecision.decision == "approved")
    )
    approved_count = approved_count_result.scalar() or 0

    rejected_count_result = await db.execute(
        select(func.count(ApprovalDecision.id)).where(ApprovalDecision.decision == "rejected")
    )
    rejected_count = rejected_count_result.scalar() or 0

    total_runs_result = await db.execute(select(func.count(WorkflowRun.id)))
    total_runs = total_runs_result.scalar() or 0

    published_result = await db.execute(
        select(func.count(WorkflowRun.id)).where(WorkflowRun.status == "published")
    )
    published_count = published_result.scalar() or 0

    return {
        "pending_runs": [
            {
                "run_id": str(r.id),
                "student_id": str(r.student_id),
                "status": r.status,
                "current_step": r.current_step,
                "submitted_at": r.completed_at.isoformat() if r.completed_at else (r.created_at.isoformat() if r.created_at else None),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "resume_perfection_score": (
                    (r.result_snapshot or {}).get("resume_perfection", {}).get("evaluation", {}).get("overall_score")
                    if (r.result_snapshot or {}).get("resume_perfection", {}).get("evaluation")
                    else None
                ),
                "resume_perfection_tier": (
                    (r.result_snapshot or {}).get("resume_perfection", {}).get("evaluation", {}).get("tier_label")
                    if (r.result_snapshot or {}).get("resume_perfection", {}).get("evaluation")
                    else None
                ),
            }
            for r in runs
        ],
        "recent_decisions": [
            {
                "run_id": str(d.workflow_run_id),
                "decision": d.decision.upper(),
                "decided_at": d.reviewed_at.isoformat() if d.reviewed_at else None,
                "comments": d.comments,
            }
            for d in recent_decisions
        ],
        "stats": {
            "total_runs": total_runs,
            "pending_reviews": len(runs),
            "approval_rate_percent": round((approved_count / max(approved_count + rejected_count, 1)) * 100, 1),
            "published_versions": published_count,
        },
    }


@router.get("/{workflow_run_id}/report")
async def get_run_report(
    workflow_run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    MVP: Get the result_snapshot for a workflow run (officer review).
    No authentication required for MVP.

    SECURITY REQUIREMENT: To be locked down with `require_role("placement_officer")`
    in Phase 3 / Production.
    """
    result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found.")

    return {
        "run_id": str(run.id),
        "student_id": str(run.student_id),
        "status": run.status,
        "current_step": run.current_step,
        "result_snapshot": run.result_snapshot,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


class MVPDecisionRequest(BaseModel):
    decision: str  # "approved" | "rejected"
    comments: Optional[str] = None


@router.post("/{workflow_run_id}/decide")
async def decide_run(
    workflow_run_id: uuid.UUID,
    request: MVPDecisionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    MVP: Approve or reject a workflow run (no auth required).

    SECURITY REQUIREMENT: Currently uses a generated demo officer. 
    MUST be secured with `require_role("placement_officer")` so students 
    cannot bypass the human-in-the-loop governance mechanism.

    On APPROVE:
    1. Sets WorkflowRun.status = "approved"
    2. Creates ApprovalDecision record
    3. Creates a published Version with the result_snapshot
    4. Sets WorkflowRun.status = "published"
    5. Writes AuditLog entries

    On REJECT:
    1. Sets WorkflowRun.status = "rejected"
    2. Creates ApprovalDecision record
    3. Writes AuditLog entry
    """
    valid_decisions = {"approved", "rejected"}
    if request.decision not in valid_decisions:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid decision. Must be one of: {valid_decisions}",
        )

    # Get the workflow run
    result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found.")

    if run.status not in ("pending_review", "completed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot decide on a run with status '{run.status}'. Must be 'pending_review'.",
        )

    # Get or create demo officer
    from app.api.v1.process import get_or_create_demo_officer
    officer = await get_or_create_demo_officer(db)

    correlation_id = uuid.uuid4()

    # Create approval decision
    approval = ApprovalDecision(
        workflow_run_id=workflow_run_id,
        reviewer_id=officer.id,
        decision=request.decision,
        comments=request.comments,
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add(approval)

    if request.decision == "approved":
        # 1. Mark as approved
        run.status = "approved"

        # 2. Create a published Version
        from sqlalchemy import func
        from app.models.workflow import Version

        count_result = await db.execute(
            select(func.count(Version.id)).where(
                Version.student_id == run.student_id,
                Version.entity_type == "readiness_plan",
            )
        )
        next_version_number = (count_result.scalar() or 0) + 1

        version = Version(
            student_id=run.student_id,
            entity_type="readiness_plan",
            version_number=next_version_number,
            status="published",
            snapshot=run.result_snapshot,
            workflow_run_id=workflow_run_id,
            approved_by=officer.id,
            published_at=datetime.now(timezone.utc),
        )
        db.add(version)

        # 3. Update run to published
        run.status = "published"

        # 4. Audit logs
        audit_approve = AuditLog(
            actor_id=officer.id,
            actor_type="placement_officer",
            workflow_run_id=workflow_run_id,
            action="OFFICER_APPROVED",
            entity_type="workflow_run",
            entity_id=workflow_run_id,
            decision="approved",
            approval_decision="approved",
            correlation_id=correlation_id,
            details={"comments": request.comments},
        )
        db.add(audit_approve)

        audit_version = AuditLog(
            actor_id=officer.id,
            actor_type="placement_officer",
            workflow_run_id=workflow_run_id,
            action="VERSION_CREATED",
            entity_type="version",
            version=next_version_number,
            correlation_id=correlation_id,
            details={"version_number": next_version_number, "status": "published"},
        )
        db.add(audit_version)

        audit_publish = AuditLog(
            actor_id=officer.id,
            actor_type="placement_officer",
            workflow_run_id=workflow_run_id,
            action="RESULT_PUBLISHED",
            entity_type="workflow_run",
            entity_id=workflow_run_id,
            correlation_id=correlation_id,
            details={"version_number": next_version_number},
        )
        db.add(audit_publish)

        await db.commit()
        await db.refresh(approval)

        return {
            "approval_id": str(approval.id),
            "workflow_run_id": str(workflow_run_id),
            "decision": "approved",
            "version_number": next_version_number,
            "status": "published",
            "message": "Result approved and published successfully.",
        }

    else:  # rejected
        run.status = "rejected"

        audit_reject = AuditLog(
            actor_id=officer.id,
            actor_type="placement_officer",
            workflow_run_id=workflow_run_id,
            action="OFFICER_REJECTED",
            entity_type="workflow_run",
            entity_id=workflow_run_id,
            decision="rejected",
            approval_decision="rejected",
            correlation_id=correlation_id,
            details={"comments": request.comments},
        )
        db.add(audit_reject)

        await db.commit()
        await db.refresh(approval)

        return {
            "approval_id": str(approval.id),
            "workflow_run_id": str(workflow_run_id),
            "decision": "rejected",
            "status": "rejected",
            "message": "Result rejected.",
        }

