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

@pytest.mark.asyncio
class TestResumePerfectionAPIEndpoints:
    """Test FastAPI process endpoints for resume perfection quiz."""

    async def test_invalid_uuid_returns_400(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get("/api/v1/process/runs/not-a-uuid/resume-perfection")
            assert res.status_code == 400

    async def test_non_existent_run_returns_404(self):
        from app.database import get_db
        mock_db = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_res)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                fake_id = str(uuid.uuid4())
                res = await ac.get(f"/api/v1/process/runs/{fake_id}/resume-perfection")
                assert res.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_get_and_submit_resume_perfection_flow(self):
        """End-to-end endpoint test with mock DB run."""
        from app.database import get_db

        run_id = uuid.uuid4()
        user_id = uuid.uuid4()
        student_id = uuid.uuid4()

        mock_profile = {
            "summary": "Full Stack Engineer",
            "skills": [{"name": "python", "proficiency": "advanced"}, {"name": "docker", "proficiency": "intermediate"}],
            "projects": [{"title": "Cloud Pipeline", "description": "ETL in Python", "technologies": ["Python", "Docker"]}],
            "experiences": [],
        }

        generated_questions = generate_resume_perfection_questions(mock_profile, max_questions=3)

        mock_run = WorkflowRun(
            id=run_id,
            student_id=student_id,
            initiated_by=user_id,
            status="pending_review",
            current_step="completed",
            result_snapshot={
                "student_profile": mock_profile,
                "resume_perfection": {
                    "status": "pending_submission",
                    "questions": [q.model_dump() for q in generated_questions],
                    "evaluation": None,
                },
            },
        )

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        async def mock_execute(stmt):
            mock_res = MagicMock()
            mock_res.scalar_one_or_none.return_value = mock_run
            mock_res.scalars.return_value.all.return_value = []
            return mock_res

        mock_db.execute = mock_execute
        mock_db.commit = AsyncMock()

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                # 1. Fetch questions
                get_res = await ac.get(f"/api/v1/process/runs/{run_id}/resume-perfection")
                assert get_res.status_code == 200
                data = get_res.json()
                assert data["run_id"] == str(run_id)
                assert len(data["questions"]) == 3
                assert data["status"] == "pending_submission"

                # Verify solutions are NOT leaked before submission
                for q in data["questions"]:
                    assert "correct_option_index" not in q
                    assert "explanation" not in q

                # 2. Submit answers using actual known correct indices
                correct_map = {q.id: q.correct_option_index for q in generated_questions}
                answers_payload = {
                    "answers": [
                        {
                            "question_id": q["id"],
                            "selected_option_index": correct_map[q["id"]],
                            "student_notes": "Implemented this directly.",
                        }
                        for q in data["questions"]
                    ]
                }
                sub_res = await ac.post(
                    f"/api/v1/process/runs/{run_id}/resume-perfection/submit",
                    json=answers_payload,
                )
                assert sub_res.status_code == 200
                eval_data = sub_res.json()
                assert eval_data["status"] == "evaluated"
                assert eval_data["evaluation"]["overall_score"] == 100.0
                assert eval_data["evaluation"]["perfection_tier"] == "exceptional"

                # 3. Regenerate questions
                regen_res = await ac.post(f"/api/v1/process/runs/{run_id}/resume-perfection/regenerate")
                assert regen_res.status_code == 200
                assert regen_res.json()["status"] == "pending_submission"
                assert len(regen_res.json()["questions"]) > 0
                for q in regen_res.json()["questions"]:
                    assert "correct_option_index" not in q
                    assert "explanation" not in q

        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_dashboard_endpoint_includes_resume_perfection(self):
        """Dashboard endpoint returns resume_perfection object."""
        from app.database import get_db

        run_id = uuid.uuid4()
        mock_run = WorkflowRun(
            id=run_id,
            student_id=uuid.uuid4(),
            initiated_by=uuid.uuid4(),
            status="published",
            current_step="completed",
            result_snapshot={
                "student_profile": {"summary": "CS Student", "skills": [], "projects": [], "experiences": []},
                "resume_perfection": {
                    "status": "evaluated",
                    "questions": [],
                    "evaluation": {
                        "overall_score": 90.0,
                        "perfection_tier": "exceptional",
                        "tier_label": "Verified Master",
                    },
                },
            },
        )

        mock_version = Version(
            id=uuid.uuid4(),
            workflow_run_id=run_id,
            student_id=mock_run.student_id,
            version_number=1,
            entity_type="readiness_plan",
            snapshot=mock_run.result_snapshot,
            status="published",
        )

        mock_db = AsyncMock()

        async def mock_execute(stmt):
            mock_res = MagicMock()
            # If selecting WorkflowRun
            stmt_str = str(stmt)
            if "workflow_runs" in stmt_str:
                mock_res.scalar_one_or_none.return_value = mock_run
            elif "versions" in stmt_str:
                mock_res.scalar_one_or_none.return_value = mock_version
            else:
                mock_res.scalar_one_or_none.return_value = mock_run
            return mock_res

        mock_db.execute = mock_execute

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get(f"/api/v1/dashboard/student/{run_id}")
                assert res.status_code == 200
                data = res.json()
                assert data["status"] == "published"
                assert "resume_perfection" in data["data"]
                assert data["data"]["resume_perfection"]["evaluation"]["overall_score"] == 90.0
                assert data["data"]["resume_perfection"]["evaluation"]["tier_label"] == "Verified Master"
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_officer_queue_endpoint_includes_resume_perfection_score(self):
        """Officer queue includes resume_perfection_score and tier."""
        from app.database import get_db

        run_id = uuid.uuid4()
        mock_run = WorkflowRun(
            id=run_id,
            student_id=uuid.uuid4(),
            initiated_by=uuid.uuid4(),
            status="pending_review",
            current_step="completed",
            result_snapshot={
                "resume_perfection": {
                    "evaluation": {
                        "overall_score": 85.0,
                        "tier_label": "Verified Master",
                    }
                }
            },
        )

        mock_db = AsyncMock()
        calls = []

        async def mock_execute(stmt):
            mock_res = MagicMock()
            calls.append(stmt)
            if len(calls) == 1:
                mock_res.scalars.return_value.all.return_value = [mock_run]
            elif len(calls) == 2:
                mock_res.scalars.return_value.all.return_value = []
            else:
                mock_res.scalars.return_value.all.return_value = []
                mock_res.scalar.return_value = 1
            return mock_res

        mock_db.execute = mock_execute

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/v1/approvals/queue/open")
                assert res.status_code == 200
                data = res.json()
                assert len(data["pending_runs"]) == 1
                run_item = data["pending_runs"][0]
                assert run_item["resume_perfection_score"] == 85.0
                assert run_item["resume_perfection_tier"] == "Verified Master"
        finally:
            app.dependency_overrides.pop(get_db, None)
