"""
Recruitment drives stored in the database (companies, jobs, role_skills).

Officer-created drives and the Job Matching Agent read the same rows, so a
drive on the drives page is exactly what students are matched against.
"""
import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.company import Company, Job, RoleSkill
from app.models.profile import Skill
from app.schemas.company import CompanyCreate, CompanyUpdate, JobDriveResponse, RecruitmentRound
from app.services.reference_data import get_or_create_skill


def _date(v: Optional[str]) -> Optional[date]:
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        raise ValueError(f"Invalid date '{v}', expected YYYY-MM-DD")


def drive_dict(job: Job) -> Dict[str, Any]:
    """Drive in the dict shape used by the preparedness engine and the API."""
    c = job.company
    return {
        "job_id": str(job.id),
        "company_id": str(job.company_id),
        "company_name": c.name if c else "Unknown company",
        "industry": c.industry if c else None,
        "website": c.website if c else None,
        "location": job.location or (c.location if c else None),
        "description": job.description,
        "role_title": job.title,
        "role_family": job.role_family or "software_engineering",
        "package_lpa": float(job.package_lpa) if job.package_lpa is not None else 0.0,
        "min_cgpa": float(job.min_cgpa) if job.min_cgpa is not None else 0.0,
        "max_backlogs": job.max_backlogs or 0,
        "min_experience": job.min_experience or 0,
        "required_skills": [rs.skill.name for rs in job.role_skills if rs.skill and rs.importance == "required"],
        "preferred_skills": [rs.skill.name for rs in job.role_skills if rs.skill and rs.importance != "required"],
        "drive_date": job.drive_date.isoformat() if job.drive_date else None,
        "deadline": job.deadline.isoformat() if job.deadline else None,
        "status": job.status or "upcoming",
        "selection_rounds": job.selection_rounds or [],
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


def to_response(d: Dict[str, Any]) -> JobDriveResponse:
    return JobDriveResponse(**{**d, "selection_rounds": [RecruitmentRound(**r) for r in d.get("selection_rounds") or []]})


def _query():
    return select(Job).options(selectinload(Job.role_skills).selectinload(RoleSkill.skill), selectinload(Job.company))


async def get_job(db: AsyncSession, job_id: str, refresh: bool = False) -> Optional[Job]:
    try:
        jid = uuid.UUID(str(job_id))
    except ValueError:
        return None
    q = _query().where(Job.id == jid, Job.is_active.is_(True))
    if refresh:
        q = q.execution_options(populate_existing=True)
    return (await db.execute(q)).scalar_one_or_none()


async def list_drives(db: AsyncSession, search: Optional[str] = None, role_family: Optional[str] = None,
                      status: Optional[str] = None) -> List[Dict[str, Any]]:
    q = _query().join(Company, Company.id == Job.company_id).where(Job.is_active.is_(True))
    if role_family and role_family.lower() != "all":
        q = q.where(Job.role_family == role_family)
    if status and status.lower() != "all":
        q = q.where(Job.status == status.lower())
    if search and search.strip():
        term = f"%{search.strip()}%"
        by_skill = select(RoleSkill.job_id).join(Skill, Skill.id == RoleSkill.skill_id).where(Skill.name.ilike(term))
        q = q.where(or_(Company.name.ilike(term), Job.title.ilike(term), Job.id.in_(by_skill)))
    jobs = (await db.execute(q.order_by(Job.drive_date.asc().nullslast(), Job.created_at.desc()))).scalars().all()
    return [drive_dict(j) for j in jobs]


async def _set_skills(db: AsyncSession, job: Job, required: List[str], preferred: List[str]) -> None:
    await db.execute(delete(RoleSkill).where(RoleSkill.job_id == job.id))
    seen = set()
    for importance, names in (("required", required), ("preferred", preferred)):
        for name in names:
            skill = await get_or_create_skill(db, name)
            if skill.id in seen:
                continue
            seen.add(skill.id)
            db.add(RoleSkill(job_id=job.id, skill_id=skill.id, importance=importance,
                             min_proficiency="intermediate" if importance == "required" else "beginner"))
    await db.flush()


async def _index(db: AsyncSession, job: Job, company_name: str, required: List[str], preferred: List[str]) -> None:
    """Index the listing in the knowledge base so retrieval can cite it."""
    from app.agents.knowledge_base import kb
    await kb.ingest_job_description(
        db, job.title, company_name,
        f"{job.description or ''}\nRequired skills: {', '.join(required) or 'not listed'}."
        f"\nPreferred skills: {', '.join(preferred) or 'not listed'}.",
        role_family=job.role_family,
    )


async def create_drive(db: AsyncSession, payload: CompanyCreate) -> Dict[str, Any]:
    company = (await db.execute(select(Company).where(func.lower(Company.name) == payload.name.strip().lower()))).scalar_one_or_none()
    if company is None:
        company = Company(name=payload.name.strip(), industry=payload.industry, website=payload.website,
                          location=payload.location, description=payload.description)
        db.add(company)
        await db.flush()
    job = Job(
        company_id=company.id, title=payload.role_title.strip(), role_family=payload.role_family,
        description=payload.description or f"Recruitment drive for {payload.role_title} at {payload.name}.",
        min_cgpa=payload.min_cgpa, min_experience=payload.min_experience, package_lpa=payload.package_lpa,
        location=payload.location, max_backlogs=payload.max_backlogs, drive_date=_date(payload.drive_date),
        deadline=_date(payload.deadline), status=payload.status or "upcoming", is_active=True,
        selection_rounds=[r.model_dump() for r in payload.selection_rounds] if payload.selection_rounds else [
            {"round_number": 1, "name": "Online Technical Test", "type": "coding_test", "description": "Domain basics and problem solving", "duration_minutes": 60},
            {"round_number": 2, "name": "Technical Interview", "type": "technical_interview", "description": "Required skills and projects", "duration_minutes": 45},
            {"round_number": 3, "name": "HR Interview", "type": "hr", "description": "Fit and communication", "duration_minutes": 30},
        ],
    )
    db.add(job)
    await db.flush()
    await _set_skills(db, job, payload.required_skills, payload.preferred_skills)
    await _index(db, job, company.name, payload.required_skills, payload.preferred_skills)
    await db.commit()
    return drive_dict(await get_job(db, str(job.id), refresh=True))


async def update_drive(db: AsyncSession, job_id: str, payload: CompanyUpdate) -> Optional[Dict[str, Any]]:
    job = await get_job(db, job_id)
    if job is None:
        return None
    data = payload.model_dump(exclude_unset=True)
    for key in ("name", "industry", "website"):
        if data.get(key) is not None:
            setattr(job.company, key, data[key])
    mapping = {"role_title": "title", "role_family": "role_family", "description": "description", "location": "location",
               "package_lpa": "package_lpa", "min_cgpa": "min_cgpa", "max_backlogs": "max_backlogs",
               "min_experience": "min_experience", "status": "status"}
    for key, attr in mapping.items():
        if data.get(key) is not None:
            setattr(job, attr, data[key])
    if "drive_date" in data:
        job.drive_date = _date(data["drive_date"])
    if "deadline" in data:
        job.deadline = _date(data["deadline"])
    if data.get("selection_rounds") is not None:
        job.selection_rounds = [r if isinstance(r, dict) else r.model_dump() for r in data["selection_rounds"]]
    current = drive_dict(job)
    req = data["required_skills"] if data.get("required_skills") is not None else current["required_skills"]
    pref = data["preferred_skills"] if data.get("preferred_skills") is not None else current["preferred_skills"]
    if data.get("required_skills") is not None or data.get("preferred_skills") is not None:
        await _set_skills(db, job, req, pref)
    await _index(db, job, job.company.name, req, pref)
    await db.commit()
    return drive_dict(await get_job(db, job_id, refresh=True))


async def deactivate_drive(db: AsyncSession, job_id: str) -> bool:
    """Delisting keeps the row for history but stops it being listed or matched."""
    job = await get_job(db, job_id)
    if job is None:
        return False
    job.is_active = False
    job.status = "closed"
    await db.commit()
    return True
