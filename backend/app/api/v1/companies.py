"""
Placement Cell Company Management & Student Preparedness API.

Drives are stored in the database (companies, jobs, role_skills), so the drives
page and the Job Matching Agent always use the same listings.

1. Placement Cell: list, update and close drives; cohort analytics over students' published plans.
2. Students: browse drives and self-check preparedness from their own data — never from a sample profile.
"""
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_student, get_current_user, require_role
from app.database import get_db
from app.models.user import Student, User
from app.models.workflow import Version, WorkflowRun
from app.schemas.company import (
    CohortReadinessResponse, CompanyCreate, CompanyUpdate, JobDriveResponse,
    PreparednessCheckRequest, PreparednessCheckResponse,
)
from app.services import drive_repository as repo
from app.services.company_service import company_service

router = APIRouter(prefix="/companies", tags=["Companies & Recruitment"])


@router.get("", response_model=List[JobDriveResponse], summary="List all campus recruitment drives")
async def list_recruitment_drives(
    search: Optional[str] = Query(None, description="Search by company name, role, or skill"),
    role_family: Optional[str] = Query(None, description="Filter by role domain"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (upcoming, active, closed)"),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Listed drives, for any signed-in user."""
    return [repo.to_response(d) for d in await repo.list_drives(db, search, role_family, status_filter)]


@router.get("/jobs/{job_id}", response_model=JobDriveResponse, summary="Get details of a specific recruitment drive")
async def get_recruitment_drive(job_id: str, _user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    job = await repo.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recruitment drive with id '{job_id}' not found.")
    return repo.to_response(repo.drive_dict(job))


@router.post("", response_model=JobDriveResponse, status_code=status.HTTP_201_CREATED,
             summary="Placement cell lists a new recruitment company")
async def create_recruitment_drive(
    payload: CompanyCreate,
    officer: User = Depends(require_role("placement_officer")),
    db: AsyncSession = Depends(get_db),
):
    """Saved with its skills, so students are matched against it immediately."""
    try:
        return repo.to_response(await repo.create_drive(db, payload))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.put("/jobs/{job_id}", response_model=JobDriveResponse, summary="Update an existing recruitment drive")
async def update_recruitment_drive(
    job_id: str,
    payload: CompanyUpdate,
    officer: User = Depends(require_role("placement_officer")),
    db: AsyncSession = Depends(get_db),
):
    try:
        updated = await repo.update_drive(db, job_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recruitment drive '{job_id}' not found.")
    return repo.to_response(updated)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a recruitment drive")
async def delete_recruitment_drive(
    job_id: str,
    officer: User = Depends(require_role("placement_officer")),
    db: AsyncSession = Depends(get_db),
):
    """Delist a drive (kept in the database for history; no longer listed or matched)."""
    if not await repo.deactivate_drive(db, job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recruitment drive '{job_id}' not found.")
    return None


def _from_snapshot(snap: Dict[str, Any]):
    """Profile, coding data and consented academic data from a stored plan."""
    profile = dict(snap.get("student_profile") or {})
    academic = ((snap.get("student_context") or {}).get("academic") or {})
    metadata = {"cgpa": academic.get("cgpa"),
                "coding_solved": ((snap.get("coding_analytics") or {}).get("summary") or {}).get("total_solved")}
    return profile, snap.get("coding_analytics") or {}, {k: v for k, v in metadata.items() if v is not None}


@router.post("/jobs/{job_id}/check-preparedness", response_model=PreparednessCheckResponse,
             summary="Student checks preparedness and skill match")
async def check_student_preparedness(
    job_id: str,
    payload: Optional[PreparednessCheckRequest] = None,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    Self-check against one drive using the student's OWN data: the given run (if it
    is theirs) or their latest published plan. What-if fields (skills, cgpa,
    backlogs, coding_solved, projects) can override for simulation. With no data
    and no what-if input the request is refused — no sample profile is used.
    """
    job = await repo.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recruitment drive '{job_id}' not found.")
    payload = payload or PreparednessCheckRequest()

    snap: Dict[str, Any] = {}
    if payload.run_id:
        try:
            run = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == uuid.UUID(payload.run_id)))).scalar_one_or_none()
        except ValueError:
            run = None
        if run is None or run.student_id != student.id:
            raise HTTPException(status_code=404, detail="Workflow run not found.")
        snap = run.result_snapshot or {}
    else:
        v = (await db.execute(select(Version).where(Version.student_id == student.id, Version.status == "published")
                              .order_by(Version.version_number.desc()).limit(1))).scalar_one_or_none()
        snap = (v.snapshot or {}) if v else {}

    profile, coding, metadata = _from_snapshot(snap)
    profile.setdefault("skills", [])
    profile.setdefault("projects", [])
    if payload.skills is not None:
        profile["skills"] = [{"name": s, "proficiency": "intermediate"} for s in payload.skills]
    if payload.cgpa is not None:
        profile["education"] = {"gpa": payload.cgpa}
        metadata["cgpa"] = payload.cgpa
    if payload.backlogs is not None:
        metadata["backlogs"] = payload.backlogs
    if payload.coding_solved is not None:
        metadata["coding_solved"] = payload.coding_solved
    if payload.projects is not None:
        profile["projects"] = payload.projects

    if not profile["skills"] and payload.skills is None:
        raise HTTPException(status_code=409, detail=(
            "We don't have your profile yet. Analyse your resume first, or enter skills to simulate."))

    return company_service.evaluate_student_preparedness(
        job=repo.drive_dict(job), student_profile=profile, coding_analytics=coding, metadata=metadata)


@router.get("/jobs/{job_id}/cohort-readiness", response_model=CohortReadinessResponse,
            summary="Placement cell cohort readiness analytics")
async def get_cohort_readiness_analytics(
    job_id: str,
    officer: User = Depends(require_role("placement_officer")),
    db: AsyncSession = Depends(get_db),
):
    """Eligibility and readiness for this drive across students' published plans (real students only)."""
    job = await repo.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recruitment drive '{job_id}' not found.")
    versions = (await db.execute(select(Version).where(Version.entity_type == "readiness_plan",
                                                       Version.status == "published"))).scalars().all()
    cohort = []
    for v in versions:
        profile, coding, metadata = _from_snapshot(v.snapshot or {})
        if profile.get("skills"):
            cohort.append({"student_profile": profile, "coding_analytics": coding, "metadata": metadata})
    return company_service.compute_cohort_readiness(repo.drive_dict(job), cohort)
