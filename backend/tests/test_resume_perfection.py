"""
Unit and integration tests for Resume Perfection & Authenticity Verification.

Verifies:
1. Question generation based on student's actual resume items (projects, skills, claims).
2. Edge cases (sparse profile, no projects, unusual skills).
3. Answer evaluation and perfection scoring logic.
4. Tiers and category breakdowns.
5. FastAPI process endpoints (/runs/{run_id}/resume-perfection, /submit, /regenerate).
6. Integration with Student Dashboard and Officer Approval queue.
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.services.resume_perfection_service import (
    ResumePerfectionQuestion,
    StudentAnswerItem,
    ResumePerfectionEvaluation,
    generate_resume_perfection_questions,
    evaluate_student_answers,
)
from app.models.workflow import WorkflowRun, Version
from app.models.user import User, Student
from app.main import app


# ---------------------------------------------------------------------------
# Test Question Generation
# ---------------------------------------------------------------------------

class TestResumePerfectionQuestionGeneration:
    """Test generating probing questions from parsed resume data."""

    def test_generates_questions_for_projects_and_skills(self, canonical_student_profile):
        """Should generate questions directly targeting listed projects and skills."""
        questions = generate_resume_perfection_questions(
            student_profile=canonical_student_profile,
            max_questions=5,
        )

        assert len(questions) == 5
        # Check that questions have required fields
        for q in questions:
            assert isinstance(q, ResumePerfectionQuestion)
            assert len(q.options) == 4
            assert 0 <= q.correct_option_index < 4
            assert q.question.strip()
            assert q.context.strip()
            assert q.explanation.strip()
            assert q.difficulty in ("medium", "hard", "advanced")

        # Check that project claims are referenced
        target_claims = [q.target_claim.lower() for q in questions]
        assert any("e-commerce" in c or "react" in c for c in target_claims)
        # Check that skills are referenced
        assert any("python" in c or "react" in c or "choice" in c for c in target_claims)

    def test_handles_empty_profile_gracefully(self):
        """Should fallback gracefully without throwing errors if profile is empty."""
        empty_profile = {"skills": [], "projects": [], "experiences": []}
        questions = generate_resume_perfection_questions(
            student_profile=empty_profile,
            max_questions=4,
        )

        assert len(questions) > 0
        for q in questions:
            assert len(q.options) == 4
            assert 0 <= q.correct_option_index < 4

    def test_handles_profile_with_only_skills_no_projects(self):
        """Profile with skills but zero projects."""
        profile = {
            "skills": [
                {"name": "docker", "proficiency": "advanced"},
                {"name": "postgresql", "proficiency": "intermediate"},
                {"name": "redis", "proficiency": "intermediate"},
            ],
            "projects": [],
        }
        questions = generate_resume_perfection_questions(profile, max_questions=4)
        assert len(questions) == 4
        claims = [q.target_claim.lower() for q in questions]
        assert any("docker" in c or "postgresql" in c or "redis" in c for c in claims)

    def test_handles_profile_with_only_projects_no_skills(self):
        """Profile with projects but empty skills list."""
        profile = {
            "skills": [],
            "projects": [
                {
                    "title": "Distributed Cache Cluster",
                    "description": "Built in Go with Raft consensus",
                    "technologies": ["Go", "Raft", "gRPC"],
                }
            ],
        }
        questions = generate_resume_perfection_questions(profile, max_questions=3)
        assert len(questions) == 3
        assert any("distributed cache" in q.target_claim.lower() for q in questions)

    def test_options_are_shuffled_and_distributed(self, canonical_student_profile):
        """Correct option index must NOT be statically 0 for all generated questions."""
        questions = generate_resume_perfection_questions(canonical_student_profile, max_questions=5)
        indices = [q.correct_option_index for q in questions]
        # At least one question should have correct index != 0
        assert any(idx != 0 for idx in indices), f"All indices were 0: {indices}"
        # All indices must be within 0-3
        for idx in indices:
            assert 0 <= idx < 4

    def test_multi_project_resume_generates_questions_for_all_projects(self):
        """Should generate probing questions for projects beyond the first two."""
        profile = {
            "skills": [],
            "projects": [
                {"title": "E-Commerce Gateway", "technologies": ["Go", "Kafka"]},
                {"title": "Realtime Chat Engine", "technologies": ["WebSockets", "Redis"]},
                {"title": "Compiler Optimizer", "technologies": ["LLVM", "C++"]},
            ],
        }
        questions = generate_resume_perfection_questions(profile, max_questions=3)
        assert len(questions) == 3
        claims = [q.target_claim.lower() for q in questions]
        assert any("e-commerce" in c for c in claims)
        assert any("realtime chat" in c for c in claims)
        assert any("compiler" in c for c in claims)

    def test_raw_text_used_when_profile_skills_empty(self):
        """Should scan raw_text for technology keywords when structured skills list is empty."""
        empty_profile = {"skills": [], "projects": []}
        raw_text = "Proficient in Java, Spring Boot, and AWS cloud deployments."
        questions = generate_resume_perfection_questions(
            student_profile=empty_profile,
            raw_text=raw_text,
            max_questions=3,
        )
        assert len(questions) == 3
        claims = [q.target_claim.lower() for q in questions]
        assert any("java" in c or "spring" in c or "aws" in c for c in claims)

    def test_expanded_tech_probes_cover_modern_stack(self):
        """Should match against expanded stack probes (Java, AWS, MongoDB, SQL, Git)."""
        profile = {
            "skills": [
                {"name": "java"},
                {"name": "aws"},
                {"name": "mongodb"},
                {"name": "sql"},
                {"name": "git"},
            ],
            "projects": [],
        }
        questions = generate_resume_perfection_questions(profile, max_questions=5)
        assert len(questions) == 5
        claims = [q.target_claim.lower() for q in questions]
        assert any("java" in c for c in claims)
        assert any("aws" in c for c in claims)
        assert any("mongodb" in c for c in claims)
        assert any("sql" in c for c in claims)
        assert any("git" in c for c in claims)


# ---------------------------------------------------------------------------
# Test Answer Evaluation Engine
# ---------------------------------------------------------------------------

class TestResumePerfectionAnswerEvaluation:
    """Test scoring logic, tier categorization, and feedback generation."""

    @pytest.fixture
    def sample_questions(self, canonical_student_profile):
        return generate_resume_perfection_questions(canonical_student_profile, max_questions=5)

    def test_perfect_answers_achieves_master_tier(self, sample_questions):
        """All answers correct should score 100% and tier 'Verified Master'."""
        answers = [
            StudentAnswerItem(
                question_id=q.id,
                selected_option_index=q.correct_option_index,
                student_notes="Verified against my codebase.",
            )
            for q in sample_questions
        ]

        result = evaluate_student_answers(sample_questions, answers)

        assert result.overall_score == 100.0
        assert result.correct_count == 5
        assert result.total_questions == 5
        assert result.perfection_tier == "exceptional"
        assert result.tier_label == "Verified Master"
        assert len(result.category_breakdown) > 0
        for cat in result.category_breakdown:
            assert cat.score_percentage == 100.0
        assert all(r.is_correct for r in result.question_results)

    def test_partial_answers_achieves_proficient_tier(self, sample_questions):
        """4 out of 5 correct (80%) -> Proficient Practitioner."""
        answers = []
        for i, q in enumerate(sample_questions):
            # Make the first one incorrect
            sel = (q.correct_option_index + 1) % 4 if i == 0 else q.correct_option_index
            answers.append(StudentAnswerItem(question_id=q.id, selected_option_index=sel))

        result = evaluate_student_answers(sample_questions, answers)

        assert result.overall_score == 80.0
        assert result.correct_count == 4
        assert result.perfection_tier == "proficient"
        assert result.tier_label == "Proficient Practitioner"
        assert len(result.recommendations) > 0

    def test_half_answers_achieves_surface_tier(self, sample_questions):
        """3 out of 5 correct (60%) -> Surface Familiarity."""
        answers = []
        for i, q in enumerate(sample_questions):
            sel = q.correct_option_index if i < 3 else (q.correct_option_index + 1) % 4
            answers.append(StudentAnswerItem(question_id=q.id, selected_option_index=sel))

        result = evaluate_student_answers(sample_questions, answers)

        assert result.overall_score == 60.0
        assert result.correct_count == 3
        assert result.perfection_tier == "surface"
        assert result.tier_label == "Surface Familiarity"

    def test_low_answers_achieves_inconsistent_tier(self, sample_questions):
        """1 out of 5 correct (20%) -> Claim Inconsistency."""
        answers = []
        for i, q in enumerate(sample_questions):
            sel = q.correct_option_index if i == 0 else (q.correct_option_index + 1) % 4
            answers.append(StudentAnswerItem(question_id=q.id, selected_option_index=sel))

        result = evaluate_student_answers(sample_questions, answers)

        assert result.overall_score == 20.0
        assert result.correct_count == 1
        assert result.perfection_tier == "inconsistent"
        assert result.tier_label == "Claim Inconsistency"

    def test_skipped_answers_handled_safely(self, sample_questions):
        """If student only answered 1 question out of 5."""
        answers = [
            StudentAnswerItem(
                question_id=sample_questions[0].id,
                selected_option_index=sample_questions[0].correct_option_index,
            )
        ]

        result = evaluate_student_answers(sample_questions, answers)

        assert result.total_questions == len(sample_questions)
        assert result.correct_count == 1
        # The skipped questions should be marked is_correct = False
        skipped = [r for r in result.question_results if r.question_id != sample_questions[0].id]
        for s in skipped:
            assert s.is_correct is False
            assert "skipped" in s.feedback.lower()

    def test_empty_questions_evaluation_handled_safely(self):
        """Empty question list should return 0 score and helpful recommendation without crash."""
        result = evaluate_student_answers([], [])
        assert result.overall_score == 0.0
        assert result.total_questions == 0
        assert result.correct_count == 0
        assert result.perfection_tier == "inconsistent"
        assert "no claims detected" in result.tier_label.lower()
        assert not any("verified with excellence" in r.lower() for r in result.recommendations)


# ---------------------------------------------------------------------------
# Test Process & Dashboard Endpoints
# ---------------------------------------------------------------------------

class TestResumePerfectionAPIEndpoints:
    """Resume perfection endpoints on a real run (owner-only)."""

    async def _run(self, client):
        from tests.support import grant, register_student, upload
        s = await register_student(client)
        await grant(client, s["headers"], "resume_processing")
        r = await upload(client, s["headers"])
        assert r.status_code == 200, r.text
        return s, r.json()["run_id"]

    async def test_invalid_uuid_returns_400(self, client):
        from tests.support import register_student
        s = await register_student(client)
        res = await client.get("/api/v1/process/runs/not-a-uuid/resume-perfection", headers=s["headers"])
        assert res.status_code == 400

    async def test_non_existent_or_foreign_run_returns_404(self, client, reference_data):
        from tests.support import register_student
        owner, run_id = await self._run(client)
        other = await register_student(client)
        assert (await client.get(f"/api/v1/process/runs/{uuid.uuid4()}/resume-perfection", headers=other["headers"])).status_code == 404
        assert (await client.get(f"/api/v1/process/runs/{run_id}/resume-perfection", headers=other["headers"])).status_code == 404
        assert (await client.get(f"/api/v1/process/runs/{run_id}/resume-perfection")).status_code == 401

    async def test_get_and_submit_resume_perfection_flow(self, client, reference_data):
        s, run_id = await self._run(client)
        url = f"/api/v1/process/runs/{run_id}/resume-perfection"
        got = (await client.get(url, headers=s["headers"])).json()
        assert got["questions"]
        answers = [{"question_id": q["id"], "selected_option_index": 0} for q in got["questions"]]
        res = await client.post(f"{url}/submit", json={"answers": answers}, headers=s["headers"])
        assert res.status_code == 200 and res.json()["status"] == "evaluated"

    async def test_officer_queue_includes_resume_perfection_score(self, client, db_factory, reference_data):
        from tests.support import create_officer
        s, run_id = await self._run(client)
        url = f"/api/v1/process/runs/{run_id}/resume-perfection"
        got = (await client.get(url, headers=s["headers"])).json()
        answers = [{"question_id": q["id"], "selected_option_index": 0} for q in got["questions"]]
        await client.post(f"{url}/submit", json={"answers": answers}, headers=s["headers"])
        officer = await create_officer(client, db_factory)
        queue = (await client.get("/api/v1/approvals/queue/open", headers=officer["headers"])).json()
        item = next(r for r in queue["pending_runs"] if r["run_id"] == run_id)
        assert item["resume_perfection_score"] is not None
