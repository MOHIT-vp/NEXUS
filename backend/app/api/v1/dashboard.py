"""
Lab 14 (Capstone): Dashboard API.

A single aggregated endpoint for the student frontend and an officer queue overview.
Reads only from approved, published Version snapshots — never raw agent state.
"""
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_student, get_current_user, get_db, require_role
from app.models.user import Student, User
from app.models.workflow import Version, WorkflowRun, ApprovalDecision

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class WorkflowStatusSummary(BaseModel):
    run_id: Optional[str]
    status: Optional[str]
    current_step: Optional[str]
    version_number: Optional[int]
    published_at: Optional[str]


class StudentDashboard(BaseModel):
    student_id: str
    has_approved_plan: bool
    workflow_status: WorkflowStatusSummary
    student_profile: Optional[Dict[str, Any]]
    skill_gap_report: Optional[Dict[str, Any]]
    coding_analytics: Optional[Dict[str, Any]]
    matching_result: Optional[Dict[str, Any]]
    interview_result: Optional[Dict[str, Any]]
    roadmap: Optional[Dict[str, Any]]
    resume_perfection: Optional[Dict[str, Any]] = None


class OfficerQueueSummary(BaseModel):
    pending_review_count: int
    recently_approved_count: int
    recently_rejected_count: int
    pending_runs: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Student Dashboard
# ---------------------------------------------------------------------------

@router.get("/me", response_model=StudentDashboard)
async def get_student_dashboard(
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    Aggregated student dashboard: single call returns the full current state.

    - If an approved plan exists: returns data from the latest published Version snapshot.
    - If no plan yet: returns has_approved_plan=False with null data sections.
    - workflow_status always reflects the most recent WorkflowRun for context.
    """
    # --- Latest published version ---
    version_result = await db.execute(
        select(Version)
        .where(
            Version.student_id == current_student.id,
            Version.entity_type == "readiness_plan",
            Version.status == "published",
        )
        .order_by(Version.version_number.desc())
        .limit(1)
    )
    version = version_result.scalar_one_or_none()

    # --- Most recent workflow run (for status) ---
    run_result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.student_id == current_student.id)
        .order_by(WorkflowRun.created_at.desc())
        .limit(1)
    )
    latest_run = run_result.scalar_one_or_none()

    workflow_status = WorkflowStatusSummary(
        run_id=str(latest_run.id) if latest_run else None,
        status=latest_run.status if latest_run else None,
        current_step=latest_run.current_step if latest_run else None,
        version_number=version.version_number if version else None,
        published_at=version.published_at.isoformat() if version and version.published_at else None,
    )

    if not version:
        return StudentDashboard(
            student_id=str(current_student.id),
            has_approved_plan=False,
            workflow_status=workflow_status,
            student_profile=None,
            skill_gap_report=None,
            coding_analytics=None,
            matching_result=None,
            interview_result=None,
            roadmap=None,
        )

    snap = version.snapshot
    return StudentDashboard(
        student_id=str(current_student.id),
        has_approved_plan=True,
        workflow_status=workflow_status,
        student_profile=snap.get("student_profile"),
        skill_gap_report=snap.get("skill_gap_report"),
        coding_analytics=snap.get("coding_analytics"),
        matching_result=snap.get("matching_result"),
        interview_result=snap.get("interview_result"),
        roadmap=snap.get("roadmap"),
        resume_perfection=snap.get("resume_perfection"),
    )


# ---------------------------------------------------------------------------
# Officer Queue Overview
# ---------------------------------------------------------------------------

@router.get("/officer/queue", response_model=OfficerQueueSummary)
async def get_officer_queue(
    current_user: User = Depends(require_role("placement_officer", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Officer dashboard: pending review queue and recent approval summary.
    """
    # Pending: pending_review status (awaiting officer decision)
    pending_result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.status.in_(["pending_review", "completed"]))
        .order_by(WorkflowRun.created_at.desc())
        .limit(20)
    )
    pending_runs = pending_result.scalars().all()

    # Approved count (recent decisions)
    approved_result = await db.execute(
        select(func.count(ApprovalDecision.id)).where(ApprovalDecision.decision == "approved")
    )
    approved_count = approved_result.scalar() or 0

    # Rejected count
    rejected_result = await db.execute(
        select(func.count(ApprovalDecision.id)).where(ApprovalDecision.decision == "rejected")
    )
    rejected_count = rejected_result.scalar() or 0

    return OfficerQueueSummary(
        pending_review_count=len(pending_runs),
        recently_approved_count=approved_count,
        recently_rejected_count=rejected_count,
        pending_runs=[
            {
                "run_id": str(r.id),
                "student_id": str(r.student_id),
                "status": r.status,
                "current_step": r.current_step,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in pending_runs
        ],
    )


# ---------------------------------------------------------------------------
# Unauthenticated Student Dashboard by run_id (MVP)
# ---------------------------------------------------------------------------

@router.get("/student/{run_id}")
async def get_student_dashboard_by_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    MVP endpoint: fetch dashboard data by run_id without authentication.

    - If published → returns the full Version snapshot data
    - If pending_review → returns status only (no data)
    - If running → returns status only
    - If rejected → returns status only
    """
    import uuid as uuid_mod
    try:
        run_uuid = uuid_mod.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id format.")

    result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_uuid))
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found.")

    # If not published yet, return status and any resume perfection quiz data
    if run.status not in ("published", "approved"):
        snapshot = run.result_snapshot or {}
        return {
            "status": run.status,
            "current_step": run.current_step,
            "has_approved_plan": False,
            "data": None,
            "resume_perfection": snapshot.get("resume_perfection"),
        }

    # Check for a published Version
    version_result = await db.execute(
        select(Version)
        .where(
            Version.workflow_run_id == run_uuid,
            Version.status == "published",
        )
        .order_by(Version.version_number.desc())
        .limit(1)
    )
    version = version_result.scalar_one_or_none()

    if version:
        snapshot = version.snapshot or {}
        # Build the dashboard payload from the version snapshot
        student_profile = snapshot.get("student_profile", {})
        skill_gap_report = snapshot.get("skill_gap_report", {})
        coding_analytics = snapshot.get("coding_analytics", {})
        matching_result = snapshot.get("matching_result", {})
        interview_result = snapshot.get("interview_result", {})
        roadmap = snapshot.get("roadmap", {})
        metadata = snapshot.get("metadata", {})

        matches = matching_result.get("matches", [])

        # Build roadmap items
        mapped_roadmap = []
        if isinstance(roadmap, dict) and "roadmap_items" in roadmap:
            for i, item in enumerate(roadmap["roadmap_items"]):
                mapped_roadmap.append({
                    "week": item.get("week", i + 1),
                    "skill": item.get("focus_area", "Skill"),
                    "action": item.get("action_item", "Learn"),
                    "resource": item.get("resource", "Online Course"),
                    "estimated_hours": item.get("estimated_hours", 10),
                    "priority": item.get("priority", "high"),
                })
        elif isinstance(roadmap, list):
            mapped_roadmap = roadmap

        # Build company matches for frontend
        company_matches = []
        for m in matches:
            company_matches.append({
                "job_id": m.get("job_id"),
                "company": m.get("company_name", "Unknown"),
                "role": m.get("job_title", m.get("role_title", m.get("role", "Software Engineer"))),
                "match_score": m.get("match_percentage", m.get("match_score", 0)),
                "confidence": str(m.get("confidence", 0)),
                "package_lpa": m.get("package_lpa", 0),
                "matched_skills": m.get("matched_skills", []),
                "missing_skills": m.get("missing_skills", []),
            })

        placement_score = matching_result.get("readiness_score", {}).get("total", 0)
        score_breakdown = matching_result.get("readiness_score", {})

        return {
            "status": "published",
            "has_approved_plan": True,
            "version_number": version.version_number,
            "published_at": version.published_at.isoformat() if version.published_at else None,
            "data": {
                "student_name": student_profile.get("summary", "Student").split()[0] if student_profile.get("summary") else "Student",
                "github_username": metadata.get("github_username"),
                "leetcode_handle": metadata.get("leetcode_handle"),
                "placement_score": placement_score,
                "score_breakdown": {
                    "skills": score_breakdown.get("skills", 0),
                    "coding": score_breakdown.get("coding", 0),
                    "projects": score_breakdown.get("projects", 0),
                    "cgpa": score_breakdown.get("cgpa", 0),
                },
                "skill_gaps": skill_gap_report.get("gaps", []),
                "domain_coverage": {
                    "general": skill_gap_report.get("overall_coverage", 0),
                },
                "company_matches": company_matches[:12],
                "top_companies": company_matches[:5],
                "roadmap": mapped_roadmap,
                "profile": {
                    "skills": student_profile.get("skills", []),
                    "projects": student_profile.get("projects", []),
                    "experiences": student_profile.get("experiences", []),
                    "education": student_profile.get("education"),
                    "summary": student_profile.get("summary", ""),
                },
                "resume_perfection": snapshot.get("resume_perfection"),
                "stats": {
                    "total_skills": len(student_profile.get("skills", [])),
                    "total_projects": len(student_profile.get("projects", [])),
                    "total_experiences": len(student_profile.get("experiences", [])),
                    "coding_solved": metadata.get("coding_solved", 0),
                    "gaps_open": len(skill_gap_report.get("gaps", [])),
                    "strong_matches": matching_result.get("eligible_count", 0),
                },
            },
        }

    # Approved but no version yet (edge case)
    return {
        "status": run.status,
        "has_approved_plan": False,
        "data": None,
    }

