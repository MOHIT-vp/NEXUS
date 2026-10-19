"""
Lab 11 Acceptance Suite — Pipeline Contract Tests

Full deterministic end-to-end contract tests.
Tests the pipeline spec: given valid input → all outputs present and valid.
Gate: ALL these must pass before a result can reach an officer.
"""


class TestValidationGate:
    """The ValidationAgent is the final gate before assembly."""

    def test_full_valid_state_passes_validation(self, complete_valid_state):
        """A correctly assembled state must pass every error-severity validation check."""
        from app.agents.validation_agent import validation_agent_node
        result = validation_agent_node(complete_valid_state)

        report = result.get("validation_report", {})
        assert report.get("total_checks") == 18, \
            f"Expected 18 checks, got {report.get('total_checks')}"
        assert result.get("validation_passed") or report.get("error_failures", 0) == 0, \
            f"Unexpected error failures: {report.get('checks', [])}"

    def test_missing_consent_fails(self, complete_valid_state):
        """Missing consent must always fail validation."""
        from app.agents.validation_agent import validation_agent_node
        state = {**complete_valid_state, "consent_validated": False}
        result = validation_agent_node(state)
        assert "CONSENT_SATISFIED" in result.get("failing_checks", []), (
            f"Expected CONSENT_SATISFIED in failing_checks, got: {result.get('failing_checks')}"
        )

    def test_missing_profile_fails(self, complete_valid_state):
        """Missing student_profile must fail NO_MISSING_SECTIONS."""
        from app.agents.validation_agent import validation_agent_node
        state = {**complete_valid_state, "student_profile": None}
        result = validation_agent_node(state)
        assert not result.get("validation_passed")
        assert "NO_MISSING_SECTIONS" in result.get("failing_checks", []), (
            f"Expected NO_MISSING_SECTIONS in failing_checks, got: {result.get('failing_checks')}"
        )

    def test_missing_skill_gap_fails(self, complete_valid_state):
        """Missing skill_gap_report must fail SECTIONS_PRESENT."""
        from app.agents.validation_agent import validation_agent_node
        state = {**complete_valid_state, "skill_gap_report": None}
        result = validation_agent_node(state)
        assert not result.get("validation_passed")

    def test_no_evidence_fails(self, complete_valid_state):
        """Empty evidence_records must fail EVIDENCE_PRESENT."""
        from app.agents.validation_agent import validation_agent_node
        state = {**complete_valid_state, "evidence_records": []}
        result = validation_agent_node(state)
        assert "EVIDENCE_PRESENT" in result.get("failing_checks", [])

    def test_diagnosis_produced_on_failure(self, complete_valid_state):
        """A failed validation must produce a diagnosis with agents_to_regenerate."""
        from app.agents.validation_agent import validation_agent_node
        state = {**complete_valid_state, "consent_validated": False}
        result = validation_agent_node(state)
        report = result.get("validation_report", {})
        assert "diagnosis" in report, "No diagnosis produced on failure"
        diag = report["diagnosis"]
        assert "agents_to_regenerate" in diag
        assert "can_self_heal" in diag


class TestSkillGapContract:
    """Deterministic skill gap computations must be consistent."""

    @staticmethod
    def _import_skill_gap():
        """Import skill gap helpers, mocking config if pydantic_settings is absent."""
        import sys
        import types
        if "pydantic_settings" not in sys.modules:
            mock_ps = types.ModuleType("pydantic_settings")
            class _BaseSettings:
                pass
            mock_ps.BaseSettings = _BaseSettings
            sys.modules["pydantic_settings"] = mock_ps
        if "app.config" not in sys.modules:
            mock_cfg = types.ModuleType("app.config")
            class _Settings:
                LLM_MODEL = "gemini-1.5-flash"
                LLM_API_KEY = "dummy"
            mock_cfg.settings = _Settings()
            sys.modules["app.config"] = mock_cfg
        from app.agents.skill_gap_agent import _compute_skill_coverage
        return _compute_skill_coverage

    def test_full_coverage_with_all_skills(self):
        _compute_skill_coverage = self._import_skill_gap()
        student = [
            {"name": "python", "proficiency": "advanced"},
            {"name": "javascript", "proficiency": "intermediate"},
        ]
        required = [
            {"skill_name": "Python", "expected_level": "intermediate",
             "importance": "required", "source": "test"},
            {"skill_name": "JavaScript", "expected_level": "intermediate",
             "importance": "required", "source": "test"},
        ]
        result = _compute_skill_coverage(student, required)
        assert result["overall_coverage"] == 100.0
        assert len(result["gaps"]) == 0

    def test_zero_coverage_with_no_matching_skills(self):
        _compute_skill_coverage = self._import_skill_gap()
        student = [{"name": "photoshop", "proficiency": "advanced"}]
        required = [
            {"skill_name": "Python", "expected_level": "intermediate",
             "importance": "required", "source": "test"},
        ]
        result = _compute_skill_coverage(student, required)
        assert result["overall_coverage"] == 0.0
        assert len(result["gaps"]) == 1

    def test_partial_coverage(self):
        _compute_skill_coverage = self._import_skill_gap()
        student = [
            {"name": "python", "proficiency": "advanced"},
            {"name": "sql", "proficiency": "beginner"},
        ]
        required = [
            {"skill_name": "Python", "expected_level": "intermediate",
             "importance": "required", "source": "test"},
            {"skill_name": "Docker", "expected_level": "beginner",
             "importance": "required", "source": "test"},
        ]
        result = _compute_skill_coverage(student, required)
        assert result["overall_coverage"] == 50.0


class TestJobMatchingContract:
    """Scoring engine must behave deterministically."""

    @staticmethod
    def _import_job_matching():
        import sys
        import types
        if "pydantic_settings" not in sys.modules:
            mock_ps = types.ModuleType("pydantic_settings")
            class _BaseSettings:
                pass
            mock_ps.BaseSettings = _BaseSettings
            sys.modules["pydantic_settings"] = mock_ps
        if "app.config" not in sys.modules:
            mock_cfg = types.ModuleType("app.config")
            class _Settings:
                LLM_MODEL = "gemini-1.5-flash"
                LLM_API_KEY = "dummy"
            mock_cfg.settings = _Settings()
            sys.modules["app.config"] = mock_cfg
        from app.agents.job_matching_agent import (
            _check_eligibility,
            _compute_skill_coverage_score,
            _compute_coding_performance_score,
        )
        return _check_eligibility, _compute_skill_coverage_score, _compute_coding_performance_score

    def test_eligible_with_meeting_gpa(self):
        _check_eligibility, _, _ = self._import_job_matching()
        profile = {"education": {"gpa": 8.0}, "years_experience": 0}
        job = {"min_cgpa": 7.0, "min_experience": 0}
        score, is_eligible, _ = _check_eligibility(profile, job, 5)
        assert is_eligible
        assert score == 5

    def test_ineligible_below_gpa(self):
        _check_eligibility, _, _ = self._import_job_matching()
        profile = {"education": {"gpa": 6.5}, "years_experience": 0}
        job = {"min_cgpa": 7.0, "min_experience": 0}
        score, is_eligible, _ = _check_eligibility(profile, job, 5)
        assert not is_eligible
        assert score == 0

    def test_readiness_score_bounded(self):
        _, _compute_skill_coverage_score, _compute_coding_performance_score = self._import_job_matching()
        student_skills = [{"name": "python"}, {"name": "javascript"}]
        score, _ = _compute_skill_coverage_score(student_skills, ["Python"], ["JavaScript"], 40)
        assert 0 <= score <= 40

        coding = {"summary": {"coding_percentile": 85.0, "difficulty_score": 70.0,
                              "activity_trend": "improving"}}
        cscore, _ = _compute_coding_performance_score(coding, 25)
        assert 0 <= cscore <= 25


class TestSelfHealingContract:
    """Self-healing must correctly route to the failing agent."""

    def test_heal_routes_to_skill_gap(self):
        from app.agents.self_healing import diagnose_and_regenerate, regeneration_route
        state = {
            "retry_count": 0, "max_retries": 3,
            "failing_checks": ["SKILL_GAP_CITATION"],
            "validation_report": {
                "diagnosis": {
                    "agents_to_regenerate": ["skill_gap_agent"],
                    "failed_error_checks": ["SKILL_GAP_CITATION"],
                    "failed_warning_checks": [], "unresolvable": [], "can_self_heal": True,
                }
            },
            "student_id": "s1", "budget_remaining": 100000,
        }
        result = diagnose_and_regenerate(state)
        assert result["healing_target"] == "skill_gap_agent"
        assert regeneration_route(result) == "skill_gap_agent"

    def test_escalates_when_no_retries(self):
        from app.agents.self_healing import validation_route
        assert validation_route({
            "validation_passed": False, "retry_count": 3,
            "max_retries": 3, "budget_remaining": 100000,
        }) == "fail_escalate"

    def test_retries_when_budget_available(self):
        from app.agents.self_healing import validation_route
        assert validation_route({
            "validation_passed": False, "retry_count": 1,
            "max_retries": 3, "budget_remaining": 100000,
        }) == "fail_retry"
