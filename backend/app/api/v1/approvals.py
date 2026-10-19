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
    current_user: User = Depends(require_role("placement_officer")),
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


@router.post("/{workflow_run_id}", status_code=status.HTTP_201_CREATED)
async def submit_approval(
    workflow_run_id: uuid.UUID,
    request: ApprovalRequest,
    current_user: User = Depends(require_role("placement_officer")),
    db: AsyncSession = Depends(get_db),
):
    """
    Older decision route. It applies exactly the same rules as /decide (validation
    gate, officer-only); edits must go through /edit so they are re-validated.
    """
    if request.decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=422, detail="Use 'approved' or 'rejected' (edits go through /edit).")
    return await decide_run(workflow_run_id, MVPDecisionRequest(decision=request.decision, comments=request.comments),
                            current_user, db)


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
    from app.api.deps import can_view_run
    run = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id))).scalar_one_or_none()
    if run is None or not await can_view_run(db, current_user, run):
        raise HTTPException(status_code=404, detail="Workflow run not found")
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
# Placement Cell console endpoints (used by the officer page)
#
# Every endpoint requires an authenticated user with the placement_officer role.
# Only runs that passed validation are in the queue, and only the officer can
# approve, edit, override or reject. Students and agents cannot reach these.
# ---------------------------------------------------------------------------

def _validation(run: WorkflowRun) -> Dict[str, Any]:
    return (run.result_snapshot or {}).get("validation_report") or {}


def _failing(report: Dict[str, Any], severity: str) -> List[str]:
    return [c["code"] for c in report.get("checks", []) if not c.get("passed") and c.get("severity") == severity]


async def _get_run(db: AsyncSession, run_id: uuid.UUID) -> WorkflowRun:
    run = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found.")
    return run


@router.get("/queue/open")
async def get_open_approval_queue(
    officer: User = Depends(require_role("placement_officer")),
    db: AsyncSession = Depends(get_db),
):
    """Runs awaiting review (validation already passed), recent decisions and counts."""
    from sqlalchemy import func
    from app.models.user import Student
    from app.models.workflow import Version

    runs = (await db.execute(
        select(WorkflowRun).where(WorkflowRun.status == "pending_review")
        .order_by(WorkflowRun.created_at.desc()).limit(50)
    )).scalars().all()
    names = dict((await db.execute(
        select(Student.id, User.full_name).join(User, User.id == Student.user_id)
        .where(Student.id.in_([r.student_id for r in runs] or [uuid.uuid4()]))
    )).all())

    recent_decisions = (await db.execute(
        select(ApprovalDecision).order_by(ApprovalDecision.reviewed_at.desc()).limit(10)
    )).scalars().all()

    # For each approved decision, find the student's previous version so the UI can offer rollback
    rollback_targets: Dict[uuid.UUID, Optional[str]] = {}
    for d in recent_decisions:
        if d.decision not in ("approved", "override"):
            continue
        current = (await db.execute(select(Version).where(Version.workflow_run_id == d.workflow_run_id)
                                    .order_by(Version.version_number.desc()).limit(1))).scalar_one_or_none()
        if current is None:
            continue
        previous = (await db.execute(select(Version).where(
            Version.student_id == current.student_id, Version.entity_type == current.entity_type,
            Version.version_number < current.version_number, Version.status != "rolled_back",
        ).order_by(Version.version_number.desc()).limit(1))).scalar_one_or_none()
        if previous is not None and current.status == "published":
            rollback_targets[d.workflow_run_id] = str(previous.id)

    counts = dict((await db.execute(
        select(ApprovalDecision.decision, func.count(ApprovalDecision.id)).group_by(ApprovalDecision.decision)
    )).all())
    approved_count = counts.get("approved", 0) + counts.get("override", 0)
    rejected_count = counts.get("rejected", 0)
    total_runs = (await db.execute(select(func.count(WorkflowRun.id)))).scalar() or 0
    published_count = (await db.execute(
        select(func.count(WorkflowRun.id)).where(WorkflowRun.status == "published"))).scalar() or 0
    failed_count = (await db.execute(
        select(func.count(WorkflowRun.id)).where(WorkflowRun.status == "validation_failed"))).scalar() or 0

    def perf(r, key):
        ev = ((r.result_snapshot or {}).get("resume_perfection") or {}).get("evaluation")
        return ev.get(key) if ev else None

    return {
        "pending_runs": [
            {
                "run_id": str(r.id),
                "student_id": str(r.student_id),
                "student_name": names.get(r.student_id),
                "status": r.status,
                "current_step": r.current_step,
                "submitted_at": r.completed_at.isoformat() if r.completed_at else (r.created_at.isoformat() if r.created_at else None),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "resume_perfection_score": perf(r, "overall_score"),
                "resume_perfection_tier": perf(r, "tier_label"),
                "target_roles": (r.result_snapshot or {}).get("target_roles", []),
                "checks_passed": _validation(r).get("passed_checks"),
                "total_checks": _validation(r).get("total_checks"),
                "warnings": _failing(_validation(r), "warning"),
                "gaps": [g.get("skill") for g in ((r.result_snapshot or {}).get("skill_gap_report") or {}).get("gaps", [])][:12],
            }
            for r in runs
        ],
        "recent_decisions": [
            {
                "run_id": str(d.workflow_run_id),
                "decision": d.decision.upper(),
                "decided_at": d.reviewed_at.isoformat() if d.reviewed_at else None,
                "comments": d.comments,
                "rollback_to_version_id": rollback_targets.get(d.workflow_run_id),
            }
            for d in recent_decisions
        ],
        "stats": {
            "total_runs": total_runs,
            "pending_reviews": len(runs),
            "validation_failed": failed_count,
            "approval_rate_percent": round((approved_count / max(approved_count + rejected_count, 1)) * 100, 1),
            "published_versions": published_count,
        },
    }


@router.get("/{workflow_run_id}/report")
async def get_run_report(
    workflow_run_id: uuid.UUID,
    officer: User = Depends(require_role("placement_officer")),
    db: AsyncSession = Depends(get_db),
):
    """The assembled draft and its validation report for officer review."""
    run = await _get_run(db, workflow_run_id)
    return {
        "run_id": str(run.id),
        "student_id": str(run.student_id),
        "status": run.status,
        "current_step": run.current_step,
        "result_snapshot": run.result_snapshot,
        "validation_report": _validation(run),
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


class MVPDecisionRequest(BaseModel):
    decision: str  # "approved" | "rejected"
    comments: Optional[str] = None


class EditRequest(BaseModel):
    officer_note: Optional[str] = None
    gap_recommendations: Optional[Dict[str, str]] = None  # {skill: new recommendation}


class OverrideRequest(BaseModel):
    reason: str
    comments: Optional[str] = None


async def _publish(db: AsyncSession, run: WorkflowRun, officer: User, decision: str,
                   comments: Optional[str], extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Approve the run and publish its assembled draft as a new Version."""
    from sqlalchemy import func
    from app.models.workflow import Version

    correlation_id = uuid.uuid4()
    approval = ApprovalDecision(workflow_run_id=run.id, reviewer_id=officer.id, decision=decision,
                                comments=comments, edits=extra, reviewed_at=datetime.now(timezone.utc))
    db.add(approval)
    next_version_number = ((await db.execute(select(func.max(Version.version_number)).where(
        Version.student_id == run.student_id, Version.entity_type == "readiness_plan"))).scalar() or 0) + 1
    # Earlier published plans for this student are archived (kept for rollback)
    for v in (await db.execute(select(Version).where(
            Version.student_id == run.student_id, Version.entity_type == "readiness_plan",
            Version.status == "published"))).scalars().all():
        v.status = "archived"
    version = Version(
        student_id=run.student_id, entity_type="readiness_plan", version_number=next_version_number,
        status="published", snapshot=run.result_snapshot, workflow_run_id=run.id, approved_by=officer.id,
        published_at=datetime.now(timezone.utc),
    )
    db.add(version)
    run.status = "published"
    for action in ("OFFICER_OVERRIDE" if decision == "override" else "OFFICER_APPROVED", "VERSION_CREATED", "RESULT_PUBLISHED"):
        db.add(AuditLog(
            actor_id=officer.id, actor_type="placement_officer", workflow_run_id=run.id, action=action,
            entity_type="workflow_run", entity_id=run.id, decision="approved", approval_decision=decision,
            version=next_version_number, correlation_id=correlation_id,
            details={"comments": comments, **(extra or {})},
        ))
    await db.commit()
    await db.refresh(approval)
    return {"approval_id": str(approval.id), "workflow_run_id": str(run.id), "decision": decision,
            "version_number": next_version_number, "status": "published",
            "message": "Result approved and published successfully."}


@router.post("/{workflow_run_id}/decide")
async def decide_run(
    workflow_run_id: uuid.UUID,
    request: MVPDecisionRequest,
    officer: User = Depends(require_role("placement_officer")),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve or reject a run. Only runs that passed validation (status pending_review)
    can be decided. Approval also requires that no warning-level check failed —
    otherwise the officer must use /override with a written reason.
    """
    if request.decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=422, detail="Invalid decision. Must be 'approved' or 'rejected'.")
    run = await _get_run(db, workflow_run_id)
    if run.status != "pending_review":
        raise HTTPException(status_code=409, detail=f"Cannot decide on a run with status '{run.status}'.")

    if request.decision == "approved":
        report = _validation(run)
        if not report.get("passed"):
            raise HTTPException(status_code=409, detail="This plan failed validation and cannot be approved.")
        warnings = _failing(report, "warning")
        if warnings:
            raise HTTPException(status_code=409, detail=(
                f"Warning checks failed ({', '.join(warnings)}). Edit the plan or use Override with a reason."))
        return await _publish(db, run, officer, "approved", request.comments)

    run.status = "rejected"
    approval = ApprovalDecision(workflow_run_id=run.id, reviewer_id=officer.id, decision="rejected",
                                comments=request.comments, reviewed_at=datetime.now(timezone.utc))
    db.add(approval)
    db.add(AuditLog(actor_id=officer.id, actor_type="placement_officer", workflow_run_id=run.id,
                    action="OFFICER_REJECTED", entity_type="workflow_run", entity_id=run.id,
                    decision="rejected", approval_decision="rejected", correlation_id=uuid.uuid4(),
                    details={"comments": request.comments}))
    await db.commit()
    await db.refresh(approval)
    return {"approval_id": str(approval.id), "workflow_run_id": str(run.id), "decision": "rejected",
            "status": "rejected", "message": "Result rejected."}


@router.post("/{workflow_run_id}/edit")
async def edit_run(
    workflow_run_id: uuid.UUID,
    request: EditRequest,
    officer: User = Depends(require_role("placement_officer")),
    db: AsyncSession = Depends(get_db),
):
    """
    Officer edit: add a reviewer note and/or rewrite gap recommendations.
    The edited plan is validated again; if it fails it leaves the queue.
    """
    import copy
    from sqlalchemy.orm.attributes import flag_modified
    from app.agents.validation_agent import validation_agent_node

    run = await _get_run(db, workflow_run_id)
    if run.status not in ("pending_review", "validation_failed"):
        raise HTTPException(status_code=409, detail=f"Cannot edit a run with status '{run.status}'.")
    snapshot = copy.deepcopy(run.result_snapshot or {})
    changes = []
    if request.officer_note and request.officer_note.strip():
        snapshot.setdefault("officer_notes", []).append(
            {"by": officer.full_name, "at": datetime.now(timezone.utc).isoformat(), "note": request.officer_note.strip()})
        changes.append({"field": "officer_notes", "after": request.officer_note.strip()})
    for skill, text in (request.gap_recommendations or {}).items():
        gap = next((g for g in (snapshot.get("skill_gap_report") or {}).get("gaps", []) if g.get("skill") == skill), None)
        if gap is None:
            raise HTTPException(status_code=422, detail=f"No gap named '{skill}' in this plan.")
        changes.append({"field": f"gap:{skill}", "before": gap.get("recommendation"), "after": text.strip()})
        gap["recommendation"] = text.strip()
        gap["edited_by_officer"] = True
    if not changes:
        raise HTTPException(status_code=422, detail="Nothing to edit.")

    report = validation_agent_node(snapshot)["validation_report"]
    snapshot["validation_report"] = report
    snapshot.setdefault("metadata", {})["validation_passed"] = report["passed"]
    run.result_snapshot = snapshot
    flag_modified(run, "result_snapshot")
    run.status = "pending_review" if report["passed"] else "validation_failed"
    db.add(ApprovalDecision(workflow_run_id=run.id, reviewer_id=officer.id, decision="edited",
                            edits={"changes": changes}, reviewed_at=datetime.now(timezone.utc)))
    db.add(AuditLog(actor_id=officer.id, actor_type="placement_officer", workflow_run_id=run.id,
                    action="OFFICER_EDITED", entity_type="workflow_run", entity_id=run.id,
                    correlation_id=uuid.uuid4(), details={"changes": changes, "validation_passed": report["passed"]}))
    await db.commit()
    return {"workflow_run_id": str(run.id), "status": run.status, "changes": changes,
            "validation_passed": report["passed"],
            "failing_checks": [c["code"] for c in report["checks"] if not c["passed"]]}


@router.post("/{workflow_run_id}/override")
async def override_run(
    workflow_run_id: uuid.UUID,
    request: OverrideRequest,
    officer: User = Depends(require_role("placement_officer")),
    db: AsyncSession = Depends(get_db),
):
    """
    Officer override: publish a plan whose only failed checks are warnings, with a
    written reason (min 20 characters) recorded in the audit log. Error-level
    checks (consent, grounding, eligibility, data isolation) can never be overridden.
    """
    run = await _get_run(db, workflow_run_id)
    if run.status != "pending_review":
        raise HTTPException(status_code=409, detail=f"Cannot override a run with status '{run.status}'.")
    if len((request.reason or "").strip()) < 20:
        raise HTTPException(status_code=422, detail="Give a reason of at least 20 characters for the override.")
    report = _validation(run)
    if not report.get("passed") or _failing(report, "error"):
        raise HTTPException(status_code=409, detail="Error-level validation failures cannot be overridden.")
    return await _publish(db, run, officer, "override", request.comments,
                          {"override_reason": request.reason.strip(), "waived_checks": _failing(report, "warning")})
