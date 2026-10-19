"""
Tests for Company Listing by Placement Cell and Student Preparedness & Skill Match Feature.
"""
import uuid

import pytest
from pydantic import ValidationError
from app.schemas.company import CompanyCreate, CompanyUpdate, PreparednessCheckRequest
from app.services.company_service import company_service, CompanyService


def as_drive(payload: CompanyCreate) -> dict:
    """A drive dict in the shape the preparedness engine reads (as built from the database)."""
    d = payload.model_dump()
    d.update(job_id=str(uuid.uuid4()), company_id=str(uuid.uuid4()), company_name=d.pop("name"),
             selection_rounds=d.get("selection_rounds") or [])
    return d


class TestCompanyListingAndManagement:
    """Drives live in the database (companies, jobs, role_skills)."""

    @pytest.fixture
    async def seeded(self, db_factory):
        from scripts.seed_sample_drives import seed
        async with db_factory() as db:
            assert await seed(db) == 5
            assert await seed(db) == 0          # idempotent
        return db_factory

    async def test_list_and_search_drives(self, seeded):
        from app.services import drive_repository as repo
        async with seeded() as db:
            drives = await repo.list_drives(db)
            titles = [d["role_title"] for d in drives]
            assert len(drives) == 5 and "Software Engineer" in titles and "Data Engineer" in titles
            assert all(d["description"].startswith("[Sample company]") for d in drives)
            assert "TechCorp" in (await repo.list_drives(db, search="TechCorp"))[0]["company_name"]
            for d in await repo.list_drives(db, search="Docker"):
                assert any("docker" in s.lower() for s in d["required_skills"] + d["preferred_skills"])
            assert all(d["role_family"] == "devops" for d in await repo.list_drives(db, role_family="devops"))

    async def test_sample_drives_are_matched_by_the_job_agent(self, seeded):
        from app.connectors.job_connector import JobConnector
        async with seeded() as db:
            jobs = await JobConnector(db).list_active_jobs()
            assert len(jobs) == 5 and all(j["required_skills"] for j in jobs)

    async def test_create_update_delete_persist(self, db_factory):
        from app.connectors.job_connector import JobConnector
        from app.services import drive_repository as repo
        async with db_factory() as db:
            created = await repo.create_drive(db, CompanyCreate(
                name="Google", role_title="Software Engineer", package_lpa=32.0, min_cgpa=8.5,
                required_skills=["Python", "Algorithms"], preferred_skills=["Kubernetes"], drive_date="2026-12-15"))
            assert created["required_skills"] == ["Python", "Algorithms"]
            updated = await repo.update_drive(db, created["job_id"], CompanyUpdate(package_lpa=35.0, status="active"))
            assert updated["package_lpa"] == 35.0 and updated["status"] == "active"
        async with db_factory() as db:   # a new session = survives a restart
            assert (await repo.get_job(db, created["job_id"])) is not None
            assert await repo.deactivate_drive(db, created["job_id"])
        async with db_factory() as db:
            assert await repo.get_job(db, created["job_id"]) is None
            assert await JobConnector(db).list_active_jobs() == []

    async def test_closed_or_past_deadline_drives_not_matched(self, db_factory):
        from app.connectors.job_connector import JobConnector
        from app.services import drive_repository as repo
        async with db_factory() as db:
            await repo.create_drive(db, CompanyCreate(name="Old Co", role_title="SDE", package_lpa=5.0, deadline="2020-01-01"))
            await repo.create_drive(db, CompanyCreate(name="Shut Co", role_title="SDE", package_lpa=5.0, status="closed"))
            assert await JobConnector(db).list_active_jobs() == []

    def test_company_create_validation_constraints(self):
        """Validation constraints reject invalid packages, out-of-range CGPAs, and clean duplicate skills."""
        # Negative package
        with pytest.raises(ValidationError):
            CompanyCreate(
                name="Bad Package Corp",
                role_title="Developer",
                package_lpa=-5.0,
                min_cgpa=7.0,
            )

        # CGPA > 10.0
        with pytest.raises(ValidationError):
            CompanyCreate(
                name="Bad CGPA Corp",
                role_title="Developer",
                package_lpa=10.0,
                min_cgpa=12.5,
            )

        # Duplicate skills are deduplicated
        drive = CompanyCreate(
            name="Skill Dedupe Corp",
            role_title="Developer",
            package_lpa=10.0,
            required_skills=["Python", "python", " PYTHON ", "SQL"],
        )
        assert len(drive.required_skills) == 2
        assert "Python" in drive.required_skills
        assert "SQL" in drive.required_skills


class TestStudentPreparednessAndSkillMatch:
    """Tests for student preparedness check and skill matching with company requirements."""

    @pytest.fixture
    def sample_drive(self):
        """Create a standard test company drive."""
        payload = CompanyCreate(
            name="Amazon AWS",
            role_title="Cloud Support Associate",
            role_family="devops",
            package_lpa=16.0,
            min_cgpa=7.5,
            min_experience=0,
            required_skills=["Linux", "Networking", "Python", "Git"],
            preferred_skills=["AWS", "Docker", "Terraform"],
            drive_date="2026-11-20",
        )
        return as_drive(payload)

    def test_preparedness_high_match_student(self, sample_drive):
        """Student with all required skills and high CGPA gets a high preparedness score."""
        student_profile = {
            "skills": [
                {"name": "Linux", "proficiency": "advanced"},
                {"name": "Networking", "proficiency": "advanced"},
                {"name": "Python", "proficiency": "expert"},
                {"name": "Git", "proficiency": "intermediate"},
                {"name": "AWS", "proficiency": "intermediate"},
            ],
            "projects": [
                {"title": "Automated Cloud Setup", "technologies": ["Linux", "AWS", "Python"]},
            ],
            "education": {"gpa": 8.5},
        }
        metadata = {"coding_solved": 200}

        res = CompanyService.evaluate_student_preparedness(
            job=sample_drive,
            student_profile=student_profile,
            metadata=metadata,
        )

        assert res.is_eligible is True
        assert res.overall_score >= 70.0
        assert res.match_tier in ("Highly Prepared", "Competitive Fit")
        assert len(res.matched_skills) >= 4
        assert res.breakdown["skill_coverage"]["score"] >= 30.0
        assert res.breakdown["academic_eligibility"]["score"] == 5.0
        assert len(res.prep_roadmap) >= 2

    def test_preparedness_ineligible_cgpa(self, sample_drive):
        """Student below cutoff is flagged as ineligible with 0 academic eligibility points."""
        student_profile = {
            "skills": [
                {"name": "Linux", "proficiency": "advanced"},
                {"name": "Python", "proficiency": "advanced"},
            ],
            "education": {"gpa": 6.8},  # Below 7.5 cutoff
        }

        res = CompanyService.evaluate_student_preparedness(
            job=sample_drive,
            student_profile=student_profile,
        )

        assert res.is_eligible is False
        assert res.breakdown["academic_eligibility"]["score"] == 0.0
        assert any("below the company cutoff" in reason for reason in res.eligibility_reasons)
        assert any("Academic cutoff shortfall" in concern for concern in res.concern_areas)

    def test_preparedness_missing_skills_identified(self, sample_drive):
        """Missing required skills are properly identified as critical gaps with learning recommendations."""
        student_profile = {
            "skills": [
                {"name": "Java", "proficiency": "intermediate"},
                {"name": "HTML", "proficiency": "beginner"},
            ],
            "education": {"gpa": 8.0},
        }

        res = CompanyService.evaluate_student_preparedness(
            job=sample_drive,
            student_profile=student_profile,
        )

        assert res.overall_score < 55.0
        assert res.match_tier == "Preparation Needed"
        missing_names = [m.skill for m in res.missing_skills]
        assert "Linux" in missing_names
        assert "Networking" in missing_names
        assert "Python" in missing_names

        # Each missing skill has an action recommendation and resource
        for m in res.missing_skills:
            assert m.recommendation != ""
            assert m.learning_resource != ""
            assert m.estimated_hours > 0

    def test_tailored_prep_roadmap_generated(self, sample_drive):
        """The 2-week preparation roadmap provides weekly structured milestones."""
        student_profile = {
            "skills": [{"name": "Python", "proficiency": "intermediate"}],
            "education": {"gpa": 7.8},
        }

        res = CompanyService.evaluate_student_preparedness(
            job=sample_drive,
            student_profile=student_profile,
        )

        assert len(res.prep_roadmap) >= 2
        weeks = [item["week"] for item in res.prep_roadmap]
        assert 1 in weeks
        assert 2 in weeks
        # Week 1 prioritizes gap closure
        assert "Linux" in res.prep_roadmap[0]["focus_area"] or "Networking" in res.prep_roadmap[0]["focus_area"] or "Python" in res.prep_roadmap[0]["focus_area"]


    def test_canonical_skill_alias_matching(self):
        """Student skills with common aliases (e.g. React vs React.js, k8s vs Kubernetes, cpp vs C++) match correctly."""
        drive = CompanyCreate(
            name="Modern Cloud Corp",
            role_title="Platform Engineer",
            package_lpa=18.0,
            min_cgpa=7.0,
            required_skills=["React.js", "Kubernetes", "C++", "AWS"],
            preferred_skills=["Docker"],
        )
        drive = as_drive(drive)

        student_profile = {
            "skills": [
                {"name": "React", "proficiency": "advanced"},
                {"name": "k8s", "proficiency": "intermediate"},
                {"name": "cpp", "proficiency": "advanced"},
                {"name": "amazon web services", "proficiency": "intermediate"},
            ],
            "education": {"gpa": 8.0},
        }

        res = CompanyService.evaluate_student_preparedness(
            job=drive,
            student_profile=student_profile,
        )

        assert len(res.matched_skills) == 4
        matched_names = {m["name"] for m in res.matched_skills}
        assert "React.js" in matched_names
        assert "Kubernetes" in matched_names
        assert "C++" in matched_names
        assert "AWS" in matched_names
        assert len(res.missing_skills) == 1  # Docker (preferred)
        assert res.breakdown["skill_coverage"]["score"] > 30.0

    def test_backlog_cutoff_eligibility(self, sample_drive):
        """Student with active backlogs exceeding cutoff is marked ineligible."""
        student_profile = {
            "skills": [{"name": "Linux", "proficiency": "advanced"}],
            "education": {"gpa": 8.5},
        }
        # Drive requires max 0 backlogs, student has 2
        metadata = {"backlogs": 2}

        res = CompanyService.evaluate_student_preparedness(
            job=sample_drive,
            student_profile=student_profile,
            metadata=metadata,
        )

        assert res.is_cgpa_eligible is True
        assert res.is_backlog_eligible is False
        assert res.is_fully_eligible is False
        assert res.is_eligible is False
        assert res.student_backlogs == 2
        assert res.breakdown["academic_eligibility"]["score"] == 0.0
        assert any("Active backlogs count" in r for r in res.eligibility_reasons)
        assert any("Backlog clearance required" in c for c in res.concern_areas)

    def test_roadmap_addresses_preferred_skills_when_required_met(self):
        """When all required skills are matched, Week 1 focuses on high-impact preferred skills."""
        drive = CompanyCreate(
            name="Scale AI",
            role_title="ML Engineer",
            package_lpa=20.0,
            min_cgpa=7.0,
            required_skills=["Python", "Machine Learning"],
            preferred_skills=["Docker", "Kubernetes"],
        )
        drive = as_drive(drive)

        student_profile = {
            "skills": [
                {"name": "Python", "proficiency": "advanced"},
                {"name": "Machine Learning", "proficiency": "advanced"},
            ],
            "education": {"gpa": 8.0},
        }

        res = CompanyService.evaluate_student_preparedness(
            job=drive,
            student_profile=student_profile,
        )

        assert len(res.missing_skills) == 2  # Docker, Kubernetes (preferred)
        assert len(res.prep_roadmap) >= 2
        assert "Docker" in res.prep_roadmap[0]["focus_area"] or "Preferred Skill Edge" in res.prep_roadmap[0]["focus_area"]


async def _publish_plan(db_factory, user_id: str, skills, cgpa=None) -> None:
    """Store a published readiness plan for a student (what an officer approval produces)."""
    from sqlalchemy import select
    from app.models.user import Student
    from app.models.workflow import Version
    async with db_factory() as db:
        student = (await db.execute(select(Student).where(Student.user_id == uuid.UUID(user_id)))).scalar_one()
        snap = {"student_profile": {"skills": [{"name": n, "proficiency": "advanced"} for n in skills], "projects": []},
                "student_context": {"academic": {"cgpa": cgpa}} if cgpa is not None else {}}
        db.add(Version(student_id=student.id, entity_type="readiness_plan", version_number=1, status="published", snapshot=snap))
        await db.commit()


NEW_DRIVE = {
    "name": "Microsoft IDC", "industry": "Cloud & AI", "role_title": "Software Engineer",
    "role_family": "software_engineering", "package_lpa": 26.0, "min_cgpa": 8.0, "max_backlogs": 0,
    "min_experience": 0, "required_skills": ["C#", "Azure", "Algorithms", "System Design"],
    "preferred_skills": ["Kubernetes", "TypeScript"], "drive_date": "2026-11-25",
}


class TestCompanyAPIEndpoints:
    """Listing needs a signed-in user; managing drives and cohort analytics need the Placement Cell."""

    async def test_only_placement_cell_manages_drives(self, client, db_factory):
        from sqlalchemy import select
        from app.models.company import Job, RoleSkill
        from tests.support import create_officer, register_student

        assert (await client.get("/api/v1/companies")).status_code == 401
        student = await register_student(client)
        officer = await create_officer(client, db_factory)
        assert (await client.post("/api/v1/companies", json=NEW_DRIVE)).status_code == 401
        assert (await client.post("/api/v1/companies", json=NEW_DRIVE, headers=student["headers"])).status_code == 403
        created = await client.post("/api/v1/companies", json=NEW_DRIVE, headers=officer["headers"])
        assert created.status_code == 201
        job_id = created.json()["job_id"]

        async with db_factory() as db:
            job = (await db.execute(select(Job).where(Job.title == "Software Engineer"))).scalar_one()
            skills = (await db.execute(select(RoleSkill).where(RoleSkill.job_id == job.id))).scalars().all()
            assert {s.importance for s in skills} == {"required", "preferred"} and len(skills) == 6

        listed = await client.get("/api/v1/companies", headers=student["headers"])
        assert [d["job_id"] for d in listed.json()] == [job_id]
        assert (await client.put(f"/api/v1/companies/jobs/{job_id}", json={"package_lpa": 30.0},
                                 headers=student["headers"])).status_code == 403
        put = await client.put(f"/api/v1/companies/jobs/{job_id}", json={"package_lpa": 30.0}, headers=officer["headers"])
        assert put.status_code == 200 and put.json()["package_lpa"] == 30.0
        assert (await client.delete(f"/api/v1/companies/jobs/{job_id}", headers=student["headers"])).status_code == 403
        assert (await client.delete(f"/api/v1/companies/jobs/{job_id}", headers=officer["headers"])).status_code == 204
        assert (await client.get(f"/api/v1/companies/jobs/{job_id}", headers=student["headers"])).status_code == 404

    async def test_preparedness_uses_the_students_own_data(self, client, db_factory):
        from tests.support import create_officer, register_student
        officer = await create_officer(client, db_factory)
        student = await register_student(client)
        job_id = (await client.post("/api/v1/companies", json=NEW_DRIVE, headers=officer["headers"])).json()["job_id"]
        url = f"/api/v1/companies/jobs/{job_id}/check-preparedness"

        # No plan yet and nothing entered: refused instead of scoring a made-up profile
        none = await client.post(url, json={}, headers=student["headers"])
        assert none.status_code == 409 and "profile" in none.json()["detail"]
        # Officers are not students
        assert (await client.post(url, json={}, headers=officer["headers"])).status_code == 403

        # What-if simulation with explicit input still works, including an explicit empty skill list
        sim = await client.post(url, json={"skills": ["Algorithms", "C#"], "cgpa": 8.5, "backlogs": 0}, headers=student["headers"])
        assert sim.status_code == 200 and sim.json()["is_eligible"] is True
        empty = await client.post(url, json={"skills": [], "cgpa": 8.0}, headers=student["headers"])
        assert empty.status_code == 200 and empty.json()["breakdown"]["skill_coverage"]["score"] == 0.0

        # With a published plan the student's own skills and CGPA are used
        await _publish_plan(db_factory, student["user_id"], ["C#", "Azure", "Algorithms"], cgpa=7.2)
        own = (await client.post(url, json={}, headers=student["headers"])).json()
        assert {m["name"] for m in own["matched_skills"]} >= {"C#", "Azure", "Algorithms"}
        assert own["is_eligible"] is False          # 7.2 is below the 8.0 cutoff

        # Another student's run id is not accepted
        other = await register_student(client)
        assert (await client.post(url, json={"run_id": str(uuid.uuid4())}, headers=other["headers"])).status_code == 404

    async def test_cohort_readiness_uses_published_plans_only(self, client, db_factory):
        from tests.support import create_officer, register_student
        officer = await create_officer(client, db_factory)
        job_id = (await client.post("/api/v1/companies", json=NEW_DRIVE, headers=officer["headers"])).json()["job_id"]
        url = f"/api/v1/companies/jobs/{job_id}/cohort-readiness"

        empty = await client.get(url, headers=officer["headers"])
        assert empty.status_code == 200 and empty.json()["total_students_evaluated"] == 0   # no demo cohort

        a = await register_student(client)
        b = await register_student(client)
        await _publish_plan(db_factory, a["user_id"], ["C#", "Azure", "Algorithms", "System Design"], cgpa=8.6)
        await _publish_plan(db_factory, b["user_id"], ["Python"], cgpa=7.0)
        assert (await client.get(url, headers=a["headers"])).status_code == 403
        cohort = (await client.get(url, headers=officer["headers"])).json()
        assert cohort["total_students_evaluated"] == 2
        assert 0.0 < cohort["eligible_percentage"] < 100.0
