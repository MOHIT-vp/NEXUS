"""
Lab 10 Self-Healing Validation — Failure Injection Tests

Tests that verify:
1. Each validation failure is correctly diagnosed to the responsible agent.
2. The regeneration_route dispatches to the right node.
3. The retry budget correctly escalates when exhausted.
4. diagnose_and_regenerate writes the correct healing_target.

These tests are DETERMINISTIC — no LLM calls, no external dependencies.
"""


# ---------------------------------------------------------------------------
# Test 1: Skill gap citation failure → targets skill_gap_agent
# ---------------------------------------------------------------------------

def test_diagnose_skill_gap_failure():
    """SKILL_GAP_CITATION failure must map to skill_gap_agent."""
    from app.agents.validation_agent import FAILURE_TO_AGENT_MAP
    target = FAILURE_TO_AGENT_MAP.get("SKILL_GAP_CITATION")
    assert target == "skill_gap_agent", f"Expected 'skill_gap_agent', got {target!r}"


# ---------------------------------------------------------------------------
# Test 2: Eligibility enforced failure → targets job_matching_agent
# ---------------------------------------------------------------------------

def test_diagnose_eligibility_failure():
    """ELIGIBILITY_ENFORCED failure must map to job_matching_agent."""
    from app.agents.validation_agent import FAILURE_TO_AGENT_MAP
    target = FAILURE_TO_AGENT_MAP.get("ELIGIBILITY_ENFORCED")
    assert target == "job_matching_agent"


# ---------------------------------------------------------------------------
# Test 3: Evidence failure → targets evidence_grounding
# ---------------------------------------------------------------------------

def test_diagnose_evidence_failure():
    """EVIDENCE_PRESENT and CONSENT_SATISFIED are not self-healable: they escalate to the human."""
    from app.agents.validation_agent import FAILURE_TO_AGENT_MAP, _diagnose_failures
    assert FAILURE_TO_AGENT_MAP.get("EVIDENCE_PRESENT") is None
    diag = _diagnose_failures([
        {"code": "EVIDENCE_PRESENT", "passed": False, "severity": "error", "name": "x", "message": "y"},
        {"code": "CONSENT_SATISFIED", "passed": False, "severity": "error", "name": "x", "message": "y"},
    ])
    assert diag["can_self_heal"] is False
    assert set(diag["unresolvable"]) == {"EVIDENCE_PRESENT", "CONSENT_SATISFIED"}


def test_unhealable_failure_escalates_immediately():
    """validation_route must not burn retries on failures no agent can fix."""
    from app.agents.self_healing import validation_route
    state = {
        "validation_passed": False, "retry_count": 0, "max_retries": 3, "budget_remaining": 100000,
        "validation_report": {"diagnosis": {"can_self_heal": False, "agents_to_regenerate": []}},
    }
    assert validation_route(state) == "fail_escalate"


# ---------------------------------------------------------------------------
# Test 4: _diagnose_failures aggregates correctly
# ---------------------------------------------------------------------------

def test_diagnose_failures_aggregation():
    """_diagnose_failures correctly identifies all responsible agents."""
    from app.agents.validation_agent import _diagnose_failures

    failing_checks = [
        {"code": "SKILL_GAP_CITATION", "passed": False, "severity": "error", "name": "x", "message": "y"},
        {"code": "CONFIDENCE_PRESENT", "passed": False, "severity": "error", "name": "x", "message": "y"},
        {"code": "BIAS_CHECK", "passed": False, "severity": "warning", "name": "x", "message": "y"},
    ]

    diagnosis = _diagnose_failures(failing_checks)

    assert "skill_gap_agent" in diagnosis["agents_to_regenerate"]
    assert "job_matching_agent" in diagnosis["agents_to_regenerate"]
    assert "BIAS_CHECK" in diagnosis["failed_warning_checks"]
    assert "BIAS_CHECK" not in diagnosis["failed_error_checks"]


# ---------------------------------------------------------------------------
# Test 5: regeneration_route dispatches to correct nodes
# ---------------------------------------------------------------------------

def test_regeneration_router_known_targets():
    """regeneration_route must route to all known valid healing targets."""
    from app.agents.self_healing import regeneration_route

    for target in ["skill_gap_agent", "coding_analytics_agent", "job_matching_agent", "interview_agent"]:
        state = {"healing_target": target}
        result = regeneration_route(state)
        assert result == target, f"Expected {target!r}, got {result!r}"


def test_regeneration_router_unknown_target():
    """Unknown or None healing_target should fall back to validation_agent."""
    from app.agents.self_healing import regeneration_route

    for bad_target in [None, "unknown_agent", "consent_validation", ""]:
        state = {"healing_target": bad_target}
        result = regeneration_route(state)
        assert result == "validation_agent", (
            f"Expected fallback 'validation_agent' for target={bad_target!r}, got {result!r}"
        )


# ---------------------------------------------------------------------------
# Test 6: Retry budget escalation
# ---------------------------------------------------------------------------

def test_retry_budget_exhausted_escalates():
    """validation_route must return fail_escalate when retry_count >= max_retries."""
    from app.agents.self_healing import validation_route

    state = {
        "validation_passed": False,
        "retry_count": 3,
        "max_retries": 3,
        "budget_remaining": 100000,
    }
    assert validation_route(state) == "fail_escalate"


def test_retry_budget_retries_when_remaining():
    """validation_route must return fail_retry when retries are available."""
    from app.agents.self_healing import validation_route

    state = {
        "validation_passed": False,
        "retry_count": 1,
        "max_retries": 3,
        "budget_remaining": 100000,
    }
    assert validation_route(state) == "fail_retry"


def test_validation_passes_routes_to_assemble():
    """validation_route must return 'pass' when validation succeeded."""
    from app.agents.self_healing import validation_route

    state = {
        "validation_passed": True,
        "retry_count": 0,
        "max_retries": 3,
        "budget_remaining": 100000,
    }
    assert validation_route(state) == "pass"


def test_budget_exhausted_escalates():
    """validation_route must escalate when budget_remaining reaches zero."""
    from app.agents.self_healing import validation_route

    state = {
        "validation_passed": False,
        "retry_count": 0,
        "max_retries": 3,
        "budget_remaining": 0,
    }
    assert validation_route(state) == "fail_escalate"


# ---------------------------------------------------------------------------
# Test 7: diagnose_and_regenerate writes correct healing_target
# ---------------------------------------------------------------------------

def test_diagnose_node_selects_healing_target():
    """diagnose_and_regenerate must write the highest-priority failing agent to healing_target."""
    from app.agents.self_healing import diagnose_and_regenerate

    state = {
        "retry_count": 0,
        "max_retries": 3,
        "failing_checks": ["SKILL_GAP_CITATION", "ELIGIBILITY_ENFORCED"],
        "validation_report": {
            "diagnosis": {
                "agents_to_regenerate": ["job_matching_agent", "skill_gap_agent"],
                "failed_error_checks": ["SKILL_GAP_CITATION", "ELIGIBILITY_ENFORCED"],
                "failed_warning_checks": [],
                "unresolvable": [],
                "can_self_heal": True,
            }
        },
        "student_id": "test-student-0000",
        "budget_remaining": 100000,
    }

    result = diagnose_and_regenerate(state)

    # skill_gap_agent has higher priority than job_matching_agent
    assert result["healing_target"] == "skill_gap_agent", (
        f"Expected 'skill_gap_agent', got {result['healing_target']!r}"
    )
    assert result["retry_count"] == 1


# ---------------------------------------------------------------------------
# Test 8: No resolvable agents → healing_target is None → routes to validation
# ---------------------------------------------------------------------------

def test_diagnose_node_unresolvable_sets_none_target():
    """When no actionable agent is found, healing_target must be None."""
    from app.agents.self_healing import diagnose_and_regenerate

    state = {
        "retry_count": 0,
        "max_retries": 3,
        "failing_checks": ["NO_CROSS_STUDENT_LEAK"],
        "validation_report": {
            "diagnosis": {
                "agents_to_regenerate": [],
                "failed_error_checks": ["NO_CROSS_STUDENT_LEAK"],
                "failed_warning_checks": [],
                "unresolvable": ["NO_CROSS_STUDENT_LEAK"],
                "can_self_heal": False,
            }
        },
        "student_id": "test-student-0001",
        "budget_remaining": 100000,
    }

    result = diagnose_and_regenerate(state)
    assert result["healing_target"] is None


# ---------------------------------------------------------------------------
# Test 9: Full self-healing priority — interview heals last
# ---------------------------------------------------------------------------

def test_healing_priority_order():
    """skill_gap_agent must be chosen over interview_agent."""
    from app.agents.self_healing import diagnose_and_regenerate

    state = {
        "retry_count": 0,
        "max_retries": 3,
        "failing_checks": ["LOW_CONFIDENCE_FLAGGED"],
        "validation_report": {
            "diagnosis": {
                "agents_to_regenerate": ["interview_agent", "skill_gap_agent"],
                "failed_error_checks": ["LOW_CONFIDENCE_FLAGGED"],
                "failed_warning_checks": [],
                "unresolvable": [],
                "can_self_heal": True,
            }
        },
        "student_id": "test-student-0002",
        "budget_remaining": 100000,
    }

    result = diagnose_and_regenerate(state)
    assert result["healing_target"] == "skill_gap_agent"
