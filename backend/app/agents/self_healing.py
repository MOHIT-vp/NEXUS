"""
Self-Healing Logic (Lab 10) — pure Python, no LangGraph import.

Extracted from graph.py so it can be imported and unit-tested independently
without triggering the top-level `from langgraph.graph import ...` statement.
"""
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import logging

from app.agents.state import PlacementState, AuditEvent

logger = logging.getLogger(__name__)


# Priority order for picking which agent to heal first
HEALING_PRIORITY_ORDER = [
    "consent_validation",
    "skill_gap_agent",
    "coding_analytics_agent",
    "job_matching_agent",
    "interview_agent",
]

VALID_HEALING_TARGETS = {
    "skill_gap_agent",
    "coding_analytics_agent",
    "job_matching_agent",
    "interview_agent",
}


def diagnose_and_regenerate(state: PlacementState) -> Dict[str, Any]:
    """
    Pure-Python implementation of the diagnose_and_regenerate logic.

    - Reads validation_report.diagnosis from state.
    - Picks the highest-priority agent to re-run.
    - Returns state patch with healing_target and incremented retry_count.
    """
    retry_count = state.get("retry_count", 0) + 1
    max_retries = state.get("max_retries", 3)

    validation_report = state.get("validation_report", {})
    diagnosis = validation_report.get("diagnosis", {})

    failing_checks = state.get("failing_checks", [])
    agents_to_regen = diagnosis.get("agents_to_regenerate", [])

    # Pick highest-priority healing target
    healing_target: Optional[str] = None
    for candidate in HEALING_PRIORITY_ORDER:
        if candidate in agents_to_regen:
            healing_target = candidate
            break
    if not healing_target and agents_to_regen:
        healing_target = agents_to_regen[0]

    audit = AuditEvent(
        action="diagnosis_completed",
        agent="DiagnoseRegenerate",
        timestamp=datetime.now(timezone.utc).isoformat(),
        details={
            "retry_count": retry_count,
            "max_retries": max_retries,
            "failing_checks": failing_checks,
            "agents_to_regenerate": agents_to_regen,
            "healing_target": healing_target,
        }
    )

    logger.info(
        f"[DiagnoseRegenerate] Retry {retry_count}/{max_retries}, "
        f"Failing: {failing_checks}, Healing target: {healing_target}"
    )

    return {
        "retry_count": retry_count,
        "healing_target": healing_target,
        "current_step": "diagnose_and_regenerate",
        "audit_events": [audit],
    }


def regeneration_route(state: PlacementState) -> str:
    """
    Pure-Python implementation of the regeneration_router logic.

    Returns the name of the next node to execute during self-healing.
    Falls back to 'validation_agent' for unknown/unresolvable targets.
    """
    target = state.get("healing_target")

    if target in VALID_HEALING_TARGETS:
        logger.info(f"[RegenerationRouter] Healing target: {target}")
        return target

    logger.warning(
        f"[RegenerationRouter] No actionable target ({target!r}), re-running validation directly"
    )
    return "validation_agent"


def validation_route(state: PlacementState) -> str:
    """
    Pure-Python implementation of the validation_router logic.

    Returns 'pass', 'fail_retry', or 'fail_escalate'.
    NOTE: Runtime budget check via `runtime` is skipped here (no side-effects in tests).
    """
    if state.get("validation_passed", False):
        return "pass"

    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    budget = state.get("budget_remaining", 100000)

    if budget <= 0:
        return "fail_escalate"

    # Failures no agent can fix (missing consent, unverifiable requirements, data
    # isolation) escalate immediately instead of burning the retry budget.
    diagnosis = (state.get("validation_report") or {}).get("diagnosis")
    if diagnosis is not None and not diagnosis.get("can_self_heal", True):
        return "fail_escalate"

    if retry_count < max_retries:
        return "fail_retry"

    return "fail_escalate"
