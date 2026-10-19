"""
Governed connector for role requirements.

Requirements come from the database only, each with its citation:
1. `skill_benchmarks` — the Placement Cell benchmark library per role
   (weight 1.0 = required, 0.5 = preferred);
2. `role_skills` on active `jobs` whose role family or title matches the target.
A target with neither is reported as `no_verified_requirements`.
"""
from typing import Any, Dict, List

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.connectors.base import BaseConnector
from app.core.roles import resolve_targets
from app.models.company import Job, RoleSkill, SkillBenchmark


class RoleConnector(BaseConnector):
    """Read access to verified role requirements."""

    async def get_role_requirements(self, target_roles: List[str]) -> List[Dict[str, Any]]:
        out = []
        for target in resolve_targets(target_roles):
            reqs: Dict[str, Dict[str, Any]] = {}
            if target["role_key"]:
                rows = (await self.safe_execute(
                    select(SkillBenchmark).options(selectinload(SkillBenchmark.skill))
                    .where(SkillBenchmark.role_family == target["role_key"])
                )).scalars().all()
                for b in rows:
                    if not b.skill:
                        continue
                    reqs[b.skill.name.lower()] = {
                        "skill_name": b.skill.name,
                        "expected_level": b.expected_level,
                        "importance": "required" if float(b.weight or 1) >= 1 else "preferred",
                        "source": b.source or "skill_benchmarks",
                    }
            conditions = [Job.title.ilike(f"%{target['title']}%")]
            if target["job_families"]:
                conditions.append(Job.role_family.in_(target["job_families"]))
            jobs = (await self.safe_execute(
                select(Job).options(selectinload(Job.role_skills).selectinload(RoleSkill.skill), selectinload(Job.company))
                .where(Job.is_active.is_(True), or_(*conditions))
            )).scalars().all()
            for job in jobs:
                cite = f"{job.company.name if job.company else 'Company'} — {job.title} (job listing)"
                for rs in job.role_skills:
                    if rs.skill and rs.skill.name.lower() not in reqs:
                        reqs[rs.skill.name.lower()] = {
                            "skill_name": rs.skill.name,
                            "expected_level": rs.min_proficiency or "intermediate",
                            "importance": rs.importance or "required",
                            "source": cite,
                        }
            out.append({**target, "status": "ok" if reqs else "no_verified_requirements",
                        "requirements": list(reqs.values())})
        return out
