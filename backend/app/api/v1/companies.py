"""
Placement Cell Company Management & Student Preparedness API.

Enables:
1. Placement Cell to list new recruitment drives coming to campus, update criteria, and view cohort analytics.
2. Students to inspect upcoming recruitment drives and evaluate their skill match and preparedness.
"""
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.company import (
    CompanyCreate,
    CompanyUpdate,
    JobDriveResponse,
    PreparednessCheckRequest,
    PreparednessCheckResponse,
    CohortReadinessResponse,
)
from app.services.company_service import company_service
from app.models.workflow import WorkflowRun, Version

router = APIRouter(prefix="/companies", tags=["Companies & Recruitment"])


# ---------------------------------------------------------------------------
# Listing & Inspection
# ---------------------------------------------------------------------------

@router.get("", response_model=List[JobDriveResponse], summary="List all campus recruitment drives")
async def list_recruitment_drives(
    search: Optional[str] = Query(None, description="Search by company name, role, or skill"),
    role_family: Optional[str] = Query(None, description="Filter by role domain (software_engineering, data_engineering, devops, etc.)"),
    status: Optional[str] = Query(None, description="Filter by status (upcoming, active, closed)"),
):
    """
    Returns all listed companies and job openings coming for recruitment.
    Accessible to students and placement officers.
    """
    return company_service.list_drives(
        search=search,
        role_family=role_family,
        status=status,
    )


@router.get("/jobs/{job_id}", response_model=JobDriveResponse, summary="Get details of a specific recruitment drive")
async def get_recruitment_drive(job_id: str):
    """
    Fetch complete job role criteria, required & preferred skills, and selection rounds.
    """
    drive = company_service.get_drive(job_id)
    if not drive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recruitment drive with id '{job_id}' not found."
        )
    return drive


# ---------------------------------------------------------------------------
# Placement Cell Management
# ---------------------------------------------------------------------------

@router.post("", response_model=JobDriveResponse, status_code=status.HTTP_201_CREATED, summary="Placement cell lists a new recruitment company")
async def create_recruitment_drive(
    payload: CompanyCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Placement Officer lists a new company coming for campus recruitment.
    Includes role specifications, package, cutoffs, required skills, and interview rounds.
    """
    created = company_service.create_drive(payload)

    # If DB is available, we can also record in database
    try:
        from app.models.company import Company as DBCompany, Job as DBJob
        new_comp = DBCompany(
            name=payload.name.strip(),
            industry=payload.industry,
            website=payload.website,
            location=payload.location,
            description=payload.description,
        )
        db.add(new_comp)
        await db.flush()

        new_job = DBJob(
            company_id=new_comp.id,
            title=payload.role_title.strip(),
            role_family=payload.role_family,
            description=payload.description,
            min_cgpa=payload.min_cgpa,
            min_experience=payload.min_experience,
            package_lpa=payload.package_lpa,
            location=payload.location,
        )
        db.add(new_job)
        await db.commit()
    except Exception:
        # Gracefully rollback if DB is in mock/offline mode
        try:
            await db.rollback()
        except Exception:
            pass

    return created


@router.put("/jobs/{job_id}", response_model=JobDriveResponse, summary="Update an existing recruitment drive")
async def update_recruitment_drive(job_id: str, payload: CompanyUpdate):
    """
    Update details, criteria, or schedule of a listed recruitment drive.
    """
    updated = company_service.update_drive(job_id, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recruitment drive '{job_id}' not found."
        )
    return updated


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a recruitment drive")
async def delete_recruitment_drive(job_id: str):
    """
    Delete or delist a recruitment drive.
    """
    deleted = company_service.delete_drive(job_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recruitment drive '{job_id}' not found."
        )
    return None


# ---------------------------------------------------------------------------
# Student Preparedness & Skill Match Check
# ---------------------------------------------------------------------------

@router.post("/jobs/{job_id}/check-preparedness", response_model=PreparednessCheckResponse, summary="Student checks preparedness and skill match")
async def check_student_preparedness(
    job_id: str,
    payload: Optional[PreparednessCheckRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Evaluates how well the student's profile matches the requirements of a specific recruitment drive.

    Evaluation includes:
    1. Overall Readiness Score (0 - 100) & Fit Tier (Highly Prepared, Competitive, Preparation Needed)
    2. Academic Eligibility & Cutoff verification (Pass/Fail CGPA margin)
    3. Deterministic component breakdown (Skills, Coding, Projects, Technical depth)
    4. Matched Skills vs Missing Skills with learning recommendations and estimated hours
    5. Actionable 2-Week Pre-Drive Roadmap tailored specifically for this company's interview rounds!
    """
    drive = company_service.get_drive(job_id)
    if not drive:
        # Fallback to ad-hoc drive creation if job_id is a campus drive/slug
        drive = company_service.get_or_create_adhoc_drive(job_id)
    if not drive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recruitment drive '{job_id}' not found."
        )

    job_dict = drive.model_dump()

    # Determine student profile:
    student_profile = {
        "skills": [],
        "projects": [],
        "education": {"gpa": None},
    }
    coding_analytics = {}
    metadata = {}

    payload = payload or PreparednessCheckRequest()

    # 1. If run_id provided, attempt to load published snapshot or workflow run
    if payload.run_id:
        try:
            run_uuid = uuid.UUID(payload.run_id)
            # Try finding published Version first
            v_res = await db.execute(
                select(Version)
                .where(Version.workflow_run_id == run_uuid, Version.status == "published")
                .order_by(Version.version_number.desc())
                .limit(1)
            )
            v = v_res.scalar_one_or_none()
            if v and v.snapshot:
                snap = v.snapshot
                student_profile = snap.get("student_profile", student_profile)
                coding_analytics = snap.get("coding_analytics", {})
                metadata = snap.get("metadata", {})
            else:
                # Fallback to WorkflowRun result_snapshot
                r_res = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_uuid))
                run = r_res.scalar_one_or_none()
                if run and run.result_snapshot:
                    snap = run.result_snapshot
                    student_profile = snap.get("student_profile", student_profile)
                    coding_analytics = snap.get("coding_analytics", {})
                    metadata = snap.get("metadata", {})
        except Exception:
            # Fallback to mock profile if DB query fails
            pass

    # 2. If student provided manual / simulated override (e.g. what-if analysis)
    explicit_skills_provided = payload.skills is not None

    if explicit_skills_provided:
        student_profile["skills"] = [
            {"name": s, "proficiency": "intermediate"} for s in (payload.skills or [])
        ]

    if payload.cgpa is not None:
        student_profile["education"] = {"gpa": payload.cgpa}
        metadata["cgpa"] = payload.cgpa

    if payload.backlogs is not None:
        metadata["backlogs"] = payload.backlogs

    if payload.coding_solved is not None:
        metadata["coding_solved"] = payload.coding_solved

    if payload.projects is not None:
        student_profile["projects"] = payload.projects

    # 3. Only populate baseline if no explicit skills provided and profile has no skills
    if not explicit_skills_provided and not student_profile.get("skills"):
        student_profile = {
            "skills": [
                {"name": "Python", "proficiency": "advanced"},
                {"name": "JavaScript", "proficiency": "intermediate"},
                {"name": "React.js", "proficiency": "intermediate"},
                {"name": "SQL", "proficiency": "intermediate"},
                {"name": "Git", "proficiency": "intermediate"},
                {"name": "Data Structures", "proficiency": "intermediate"},
            ],
            "projects": [
                {"title": "Full-Stack Web App", "technologies": ["React.js", "Python", "SQL"]},
                {"title": "Algorithmic Trading Bot", "technologies": ["Python", "Git"]},
            ],
            "education": {"gpa": payload.cgpa or 8.2},
        }
        metadata["coding_solved"] = payload.coding_solved or 120

    # Evaluate preparedness deterministically
    return company_service.evaluate_student_preparedness(
        job=job_dict,
        student_profile=student_profile,
        coding_analytics=coding_analytics,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Placement Cell Cohort Analytics
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}/cohort-readiness", response_model=CohortReadinessResponse, summary="Placement cell cohort readiness analytics")
async def get_cohort_readiness_analytics(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns aggregated placement cell insights for a company's recruitment drive:
    - Number and percentage of eligible students
    - Average readiness score across campus
    - Score distribution (High Fit, Moderate Fit, Needs Prep)
    - Top common missing skills across students to schedule targeted bootcamps!
    """
    # Attempt to gather student profiles from published versions in DB
    student_profiles = []
    try:
        v_res = await db.execute(
            select(Version)
            .where(Version.entity_type == "readiness_plan", Version.status == "published")
            .limit(50)
        )
        versions = v_res.scalars().all()
        for v in versions:
            if v.snapshot and "student_profile" in v.snapshot:
                student_profiles.append(v.snapshot["student_profile"])
    except Exception:
        pass

    try:
        return company_service.compute_cohort_readiness(
            job_id=job_id,
            student_profiles=student_profiles if student_profiles else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
