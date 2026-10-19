"""Governed connector for job listings stored in the companies/jobs tables."""
from datetime import date
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.connectors.base import BaseConnector
from app.models.company import Job, RoleSkill


def job_to_dict(job: Job) -> Dict[str, Any]:
    return {
        "job_id": str(job.id),
        "company_name": job.company.name if job.company else "Unknown company",
        "role_title": job.title,
        "role_family": job.role_family or "general",
        "package_lpa": float(job.package_lpa) if job.package_lpa is not None else None,
        "min_cgpa": float(job.min_cgpa) if job.min_cgpa is not None else 0.0,
        "min_experience": job.min_experience or 0,
        "max_backlogs": job.max_backlogs or 0,
        "deadline": job.deadline.isoformat() if job.deadline else None,
        "location": job.location,
        "required_skills": [rs.skill.name for rs in job.role_skills if rs.skill and rs.importance == "required"],
        "preferred_skills": [rs.skill.name for rs in job.role_skills if rs.skill and rs.importance != "required"],
        "source": "companies_db",
    }


class JobConnector(BaseConnector):
    """Read access to active job listings."""

    async def list_active_jobs(self) -> List[Dict[str, Any]]:
        jobs = (await self.safe_execute(
            select(Job).options(selectinload(Job.role_skills).selectinload(RoleSkill.skill), selectinload(Job.company))
            .where(Job.is_active.is_(True), Job.status.in_(["upcoming", "active"]))
            .order_by(Job.created_at.desc())
        )).scalars().all()
        today = date.today()
        # Drives whose application deadline has passed are not matched
        return [job_to_dict(j) for j in jobs if not (j.deadline and j.deadline < today)]
