"""In-memory ConnectorHub for unit-testing graph nodes without a database (tests only)."""
from typing import Any, Dict, List, Optional

from app.agents.knowledge_base import RetrievalResult, RetrievedChunk
from app.core.skills import canonical


def granted(*sources: str) -> Dict[str, Dict[str, Any]]:
    from app.services.consent import CONSENT_SOURCES
    return {s: {"status": "granted" if s in sources else "missing"} for s in CONSENT_SOURCES}


SE_REQUIREMENTS = [
    {"skill_name": "Python", "expected_level": "intermediate", "importance": "required", "source": "Benchmark v1"},
    {"skill_name": "SQL", "expected_level": "intermediate", "importance": "required", "source": "Benchmark v1"},
    {"skill_name": "Docker", "expected_level": "beginner", "importance": "preferred", "source": "Benchmark v1"},
]


class FakeHub:
    def __init__(self, *, consents=None, context=None, resume=None, coding=None, requirements=None,
                 jobs=None, resources=None):
        self.consents = consents if consents is not None else granted("resume_processing")
        self.context = context or {"career_preferences": {}, "academic": {"consented": True, "cgpa": 8.2, "active_backlogs": 0}}
        self.resume_data = resume
        self.coding = coding or {}
        self.requirements = requirements if requirements is not None else {"software_engineer": SE_REQUIREMENTS}
        self.jobs = jobs if jobs is not None else []
        self.resources = resources or {}
        self.calls: List[str] = []

    def consent_status(self, student_id):
        self.calls.append("consent")
        return self.consents

    def coding_platform(self, student_id, platform, handle=None):
        self.calls.append(f"coding.{platform}")
        return self.coding.get(platform) or {"source": platform, "status": "not_configured", "data": None,
                                             "error": "No handle provided", "retrieved_at": None}

    def role_requirements(self, target_roles):
        from app.core.roles import resolve_targets
        out = []
        for t in resolve_targets(target_roles):
            reqs = self.requirements.get(t["role_key"] or t["title"], [])
            out.append({**t, "status": "ok" if reqs else "no_verified_requirements", "requirements": reqs, "job_sources": []})
        return out

    def active_jobs(self):
        return list(self.jobs)

    def similar_prior_students(self, student_id, query_text, k=5):
        self.calls.append("similar_students")
        return list(getattr(self, "prior_students", []))

    def retrieve(self, query, *, role_families=None, doc_types=None, k=5):
        items = []
        for skill, (title, url) in self.resources.items():
            if canonical(skill) in query.lower() or skill.lower() in query.lower():
                items.append(RetrievedChunk(document_id="x", title=f"{skill}: {title}", excerpt="...", source="Test list",
                                            url=url, doc_type="learning_resource", tags=["learning_resource", canonical(skill)]))
        return RetrievalResult(status="ok" if items else "empty", backend="fake", query=query, items=items)


def job(job_id="job-1", company="Northwind", title="Software Engineer", family="software_engineering",
        required=("Python", "SQL"), preferred=("Docker",), min_cgpa=7.0, **kw) -> Dict[str, Any]:
    d = {"job_id": job_id, "company_name": company, "role_title": title, "role_family": family,
         "required_skills": list(required), "preferred_skills": list(preferred), "min_cgpa": min_cgpa,
         "max_backlogs": 0, "min_experience": 0, "package_lpa": 9.0, "source": "placement_cell",
         "application_url": "https://example.org/apply", "is_stale": False, "is_expired": False}
    d.update(kw)
    return d
