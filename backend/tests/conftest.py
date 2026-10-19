"""
Shared fixtures for the full acceptance test suite (Lab 11).

All fixtures are deterministic — no LLM calls, no external I/O.
Import path: tests/conftest.py  (auto-loaded by pytest for all test files)
"""
import os
import tempfile

# No LLM or network calls during tests; uploads go to a temporary folder
os.environ["LLM_API_KEY"] = ""
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="placement-uploads-"))
# Run checkpoints go to a throwaway file; similarity uses the no-download embeddings unless a test opts in
os.environ["CHECKPOINT_DB_PATH"] = os.path.join(tempfile.mkdtemp(prefix="placement-ckpt-"), "checkpoints.sqlite")
os.environ.setdefault("EMBEDDING_BACKEND", "hashed")

import pytest

from tests.support import *  # noqa: E402,F401,F403  (database, client and fake-connector fixtures)


# ---------------------------------------------------------------------------
# Canonical student profile
# ---------------------------------------------------------------------------

@pytest.fixture
def canonical_student_profile():
    return {
        "summary": "Final-year CS student with strong Python and web development skills.",
        "skills": [
            {"name": "python", "proficiency": "advanced"},
            {"name": "javascript", "proficiency": "intermediate"},
            {"name": "react.js", "proficiency": "intermediate"},
            {"name": "sql", "proficiency": "intermediate"},
            {"name": "git", "proficiency": "intermediate"},
        ],
        "projects": [
            {"title": "E-Commerce API", "description": "REST API with Flask + PostgreSQL",
             "technologies": ["Python", "Flask", "SQL"]},
            {"title": "React Dashboard", "description": "Analytics dashboard",
             "technologies": ["React.js", "JavaScript"]},
        ],
        "experiences": [],
        "education": {"degree": "B.Tech CS", "institution": "Test University", "gpa": 8.5},
        "flags": [],
    }


# ---------------------------------------------------------------------------
# Canonical skill gap report
# ---------------------------------------------------------------------------

@pytest.fixture
def canonical_skill_gap_report():
    return {
        "overall_coverage": 75.0,
        "overall_assessment": "competitive",
        "strengths": [
            {"skill": "Python", "level": "advanced",
             "evidence": "Benchmark: advanced required, student: advanced"},
            {"skill": "JavaScript", "level": "intermediate",
             "evidence": "Benchmark: intermediate required, student: intermediate"},
        ],
        "gaps": [
            {"skill": "Docker", "required_level": "beginner", "current_level": "missing",
             "severity": "critical",
             "recommendation": "Study Docker containerization fundamentals."},
        ],
        "citation": "JD Benchmark v2.1 — software_engineer",
    }


# ---------------------------------------------------------------------------
# Canonical coding analytics
# ---------------------------------------------------------------------------

@pytest.fixture
def canonical_coding_analytics():
    return {
        "summary": {
            "total_solved": 187,
            "coding_percentile": 72.3,
            "difficulty_score": 55.0,
            "activity_trend": "improving",
            "contest_rating": 1547,
        },
        "topic_analysis": [
            {"topic": "Arrays", "solved": 40, "total_attempted": 44,
             "accuracy": 90.9, "strength_level": "strong"},
            {"topic": "Dynamic Programming", "solved": 10, "total_attempted": 25,
             "accuracy": 40.0, "strength_level": "needs_work"},
        ],
        "trend_narration": "[AI-Generated] Consistent improvement observed.",
    }


# ---------------------------------------------------------------------------
# Canonical job matching result
# ---------------------------------------------------------------------------

@pytest.fixture
def canonical_matching_result():
    return {
        "readiness_score": {"total": 68.5, "max": 100, "percentage": 68.5},
        "matches": [
            {
                "job_id": "job-001",
                "company_name": "TechCorp",
                "role_title": "Software Engineer",
                "match_score": 68.5,
                "max_score": 100,
                "match_percentage": 68.5,
                "confidence": 0.78,
                "is_eligible": True,
                "is_low_confidence": False,
                "reasoning": "Strong Python skills match backend requirements.",
                "breakdown": [
                    {"component": "skill_coverage", "points": 28, "max": 40,
                     "details": {"required_ratio": 0.8}},
                    {"component": "coding_performance", "points": 18, "max": 25, "details": {}},
                    {"component": "project_relevance", "points": 10, "max": 15, "details": {}},
                    {"component": "interview_readiness", "points": 7.5, "max": 15, "details": {}},
                    {"component": "eligibility", "points": 5, "max": 5,
                     "details": {"is_eligible": True}},
                ],
            },
        ],
        "low_confidence_flags": [],
        "total_jobs_evaluated": 1,
        "eligible_count": 1,
    }


# ---------------------------------------------------------------------------
# Canonical interview result
# ---------------------------------------------------------------------------

@pytest.fixture
def canonical_interview_result():
    return {
        "target_role": "Software Engineer",
        "readiness_assessment": {"readiness_score": 50.2, "max_score": 100, "percentage": 65.0},
        "questions": [
            {"text": "Explain your understanding of Python's GIL.", "type": "technical",
             "difficulty": "medium", "skill_targeted": "Python",
             "expected_answer_outline": "Thread safety, CPython limitation.",
             "scoring_rubric": "Depth of understanding.", "ai_generated": True},
        ],
        "total_questions": 1,
        "mock_evaluation": {"note": "[AI-Generated]", "ai_generated_disclaimer": "Template only."},
        "preparation_tips": ["Practice LeetCode daily."],
        "ai_generated_disclaimer": "[AI-Generated] All outputs are AI-generated.",
    }


# ---------------------------------------------------------------------------
# Canonical evidence records (Lab 9)
# ---------------------------------------------------------------------------

@pytest.fixture
def canonical_evidence_records():
    return [
        {"entity_type": "student_profile", "evidence_type": "resume_parsing",
         "source": "resume_agent",
         "content": "Parsed 5 skills, 2 projects from resume.",
         "scope_tags": ["resume", "student_profile"]},
        {"entity_type": "skill_gap_report", "evidence_type": "deterministic_computation",
         "source": "skill_gap_agent",
         "content": "Coverage: 75%, Gaps: 1, Strengths: 2",
         "scope_tags": ["skill_gap", "benchmarks"]},
        {"entity_type": "coding_analytics", "evidence_type": "platform_aggregation",
         "source": "coding_analytics_agent",
         "content": "Platform: leetcode, Total Solved: 187, Rating: 1547, Percentile: 72.3%",
         "scope_tags": ["coding", "analytics"]},
        {"entity_type": "company_match", "evidence_type": "deterministic_scoring",
         "source": "job_matching_agent",
         "content": "Job: TechCorp - Software Engineer, Score: 68.5/100",
         "scope_tags": ["matching", "scoring"]},
        {"entity_type": "interview_preparation", "evidence_type": "ai_generation",
         "source": "interview_agent",
         "content": "Generated 1 questions + 3 roadmap items for Software Engineer.",
         "scope_tags": ["interview", "roadmap"]},
    ]


# ---------------------------------------------------------------------------
# Complete valid pipeline state (all agents have run)
# ---------------------------------------------------------------------------

@pytest.fixture
def complete_valid_state(
    canonical_student_profile,
    canonical_skill_gap_report,
    canonical_coding_analytics,
    canonical_matching_result,
    canonical_interview_result,
    canonical_evidence_records,
):
    return {
        "run_id": "acceptance-run-001",
        "student_id": "acceptance-student-001",
        "consent_validated": True,
        "student_profile": canonical_student_profile,
        "skill_gap_report": canonical_skill_gap_report,
        "coding_analytics": canonical_coding_analytics,
        "matching_result": canonical_matching_result,
        "interview_result": canonical_interview_result,
        "roadmap": {"items": [], "total_items": 0, "total_estimated_hours": 0},
        "evidence_records": canonical_evidence_records,
        "errors": [],
        "audit_events": [],
        "retry_count": 0,
        "max_retries": 3,
        "budget_remaining": 100000,
    }
