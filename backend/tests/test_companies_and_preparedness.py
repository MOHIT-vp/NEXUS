"""
Tests for Company Listing by Placement Cell and Student Preparedness & Skill Match Feature.
"""
import pytest
from pydantic import ValidationError
from app.schemas.company import CompanyCreate, CompanyUpdate, PreparednessCheckRequest
from app.services.company_service import company_service, CompanyService


class TestCompanyListingAndManagement:
    """Tests for Placement Cell listing and managing recruitment drives."""

    def test_list_initial_drives(self):
        """Initial seed drives should be present and valid."""
        drives = company_service.list_drives()
        assert len(drives) >= 5
        job_titles = [d.role_title for d in drives]
        assert "Software Engineer" in job_titles
        assert "Data Engineer" in job_titles

    def test_search_drives_by_company_name(self):
        """Search by company name filter."""
        drives = company_service.list_drives(search="TechCorp")
        assert len(drives) >= 1
        assert "TechCorp" in drives[0].company_name

    def test_search_drives_by_skill(self):
        """Search by skill keyword."""
        drives = company_service.list_drives(search="Docker")
        assert len(drives) >= 1
        for d in drives:
            all_skills = d.required_skills + d.preferred_skills
            assert any("docker" in s.lower() for s in all_skills)

    def test_filter_drives_by_role_family(self):
        """Filter by role family (e.g. devops, data_engineering)."""
        drives = company_service.list_drives(role_family="devops")
        assert len(drives) >= 1
        for d in drives:
            assert d.role_family == "devops"

    def test_placement_cell_create_new_company_drive(self):
        """Placement cell adds a new company coming for campus recruitment."""
        payload = CompanyCreate(
            name="Google India",
            industry="Internet & AI",
            website="https://careers.google.com",
            location="Bengaluru, India",
            description="Recruiting for Campus SWE 2026 Batch",
            role_title="Software Development Engineer I",
            role_family="software_engineering",
            package_lpa=28.5,
            min_cgpa=8.0,
            max_backlogs=0,
            min_experience=0,
            required_skills=["C++", "Python", "Data Structures", "Algorithms"],
            preferred_skills=["Distributed Systems", "Cloud Computing"],
            drive_date="2026-11-15",
            deadline="2026-11-01",
            status="upcoming",
        )

        created = company_service.create_drive(payload)
        assert created.job_id.startswith("job-")
        assert created.company_name == "Google India"
        assert created.package_lpa == 28.5
        assert created.min_cgpa == 8.0
        assert created.max_backlogs == 0
        assert "C++" in created.required_skills
        assert len(created.selection_rounds) >= 3

        # Verify it appears in search
        found = company_service.get_drive(created.job_id)
        assert found is not None
        assert found.company_name == "Google India"

    def test_placement_cell_update_drive(self):
        """Placement cell updates drive dates or package."""
        payload = CompanyCreate(
            name="Stripe Payments",
            role_title="Backend Engineer",
            package_lpa=22.0,
            min_cgpa=7.5,
            max_backlogs=1,
            required_skills=["Python", "SQL"],
        )
        created = company_service.create_drive(payload)

        update_payload = CompanyUpdate(
            package_lpa=24.0,
            status="active",
        )
        updated = company_service.update_drive(created.job_id, update_payload)
        assert updated is not None
        assert updated.package_lpa == 24.0
        assert updated.status == "active"

    def test_placement_cell_delete_drive(self):
        """Placement cell deletes or closes a drive."""
        payload = CompanyCreate(
            name="Temporary Corp",
            role_title="Intern",
            package_lpa=6.0,
            min_cgpa=6.0,
            required_skills=["Java"],
        )
        created = company_service.create_drive(payload)
        assert company_service.get_drive(created.job_id) is not None

        success = company_service.delete_drive(created.job_id)
        assert success is True
        assert company_service.get_drive(created.job_id) is None

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

    def test_get_drive_slug_and_case_fallback(self):
        """get_drive successfully resolves by case-insensitive ID, slug, and ad-hoc fallback."""
        # Exact seed ID
        d1 = company_service.get_drive("JOB-001")
        assert d1 is not None
        assert d1.company_name == "TechCorp Solutions"

        # Slug / company name match
        d2 = company_service.get_drive("job-techcorp-solutions")
        assert d2 is not None
        assert d2.company_name == "TechCorp Solutions"

        # Ad-hoc drive resolution
        adhoc = company_service.get_or_create_adhoc_drive("job-netflix-streaming", "Netflix")
        assert adhoc is not None
        assert adhoc.company_name == "Netflix"
        assert len(adhoc.required_skills) > 0


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
        return company_service.create_drive(payload).model_dump()

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
        ).model_dump()

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
        ).model_dump()

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


class TestPlacementCellCohortAnalytics:
    """Tests for placement cell cohort readiness insights."""

    def test_cohort_readiness_summary(self):
        """Placement cell can view cohort statistics for a drive."""
        drives = company_service.list_drives()
        assert len(drives) > 0
        job_id = drives[0].job_id

        cohort = company_service.compute_cohort_readiness(job_id)
        assert cohort.job_id == job_id
        assert cohort.total_students_evaluated > 0
        assert 0.0 <= cohort.eligible_percentage <= 100.0
        assert cohort.average_readiness_score > 0
        assert isinstance(cohort.common_missing_skills, list)


@pytest.mark.asyncio
class TestCompanyAPIEndpoints:
    """Tests for FastAPI HTTP routes."""

    async def test_api_list_and_check_endpoints(self):
        """Verify API endpoints respond with 200 and expected JSON structure."""
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. GET /api/v1/companies
            resp = await client.get("/api/v1/companies")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) >= 1

            first_job_id = data[0]["job_id"]

            # 2. GET /api/v1/companies/jobs/{job_id}
            resp_single = await client.get(f"/api/v1/companies/jobs/{first_job_id}")
            assert resp_single.status_code == 200
            assert resp_single.json()["job_id"] == first_job_id

            # 3. POST /api/v1/companies (Placement Cell creates new company)
            new_comp = {
                "name": "Microsoft IDC",
                "industry": "Cloud & AI",
                "role_title": "Software Engineer",
                "role_family": "software_engineering",
                "package_lpa": 26.0,
                "min_cgpa": 8.0,
                "max_backlogs": 0,
                "min_experience": 0,
                "required_skills": ["C#", "Azure", "Algorithms", "System Design"],
                "preferred_skills": ["Kubernetes", "TypeScript"],
                "drive_date": "2026-11-25",
            }
            resp_create = await client.post("/api/v1/companies", json=new_comp)
            assert resp_create.status_code == 201
            created_job_id = resp_create.json()["job_id"]
            assert resp_create.json()["company_name"] == "Microsoft IDC"

            # 4. POST /api/v1/companies/jobs/{job_id}/check-preparedness (Student checks readiness)
            check_payload = {
                "skills": ["Algorithms", "C#", "Data Structures"],
                "cgpa": 8.5,
                "backlogs": 0,
                "coding_solved": 180,
            }
            resp_check = await client.post(
                f"/api/v1/companies/jobs/{created_job_id}/check-preparedness",
                json=check_payload,
            )
            assert resp_check.status_code == 200
            check_data = resp_check.json()
            assert check_data["company_name"] == "Microsoft IDC"
            assert check_data["is_eligible"] is True
            assert check_data["is_cgpa_eligible"] is True
            assert check_data["is_backlog_eligible"] is True
            assert "breakdown" in check_data
            assert len(check_data["prep_roadmap"]) >= 2

            # 5. GET /api/v1/companies/jobs/{job_id}/cohort-readiness (Placement cell checks cohort)
            resp_cohort = await client.get(f"/api/v1/companies/jobs/{created_job_id}/cohort-readiness")
            assert resp_cohort.status_code == 200
            assert "eligible_percentage" in resp_cohort.json()

    async def test_api_explicit_empty_skills_not_overwritten(self):
        """Explicit empty skills list should be evaluated honestly as 0 matched skills, not overwritten with defaults."""
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/companies/jobs/job-001/check-preparedness",
                json={"skills": [], "cgpa": 8.0, "coding_solved": 50},
            )
            assert resp.status_code == 200
            data = resp.json()
            # Must NOT be populated with default baseline skills
            assert len(data["matched_skills"]) == 0
            assert data["breakdown"]["skill_coverage"]["score"] == 0.0
            assert data["match_tier"] == "Preparation Needed"

    async def test_api_delete_drive_returns_204(self):
        """DEL /api/v1/companies/jobs/{job_id} returns 204 No Content cleanly."""
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create a throwaway drive
            res_create = await client.post(
                "/api/v1/companies",
                json={
                    "name": "Throwaway Inc",
                    "role_title": "Intern",
                    "package_lpa": 5.0,
                },
            )
            assert res_create.status_code == 201
            job_id = res_create.json()["job_id"]

            # Delete it
            res_del = await client.delete(f"/api/v1/companies/jobs/{job_id}")
            assert res_del.status_code == 204
            assert res_del.content == b""
