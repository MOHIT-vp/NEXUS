"""
Full Node Graph — Labs 7–10 Master Orchestration Graph.

This is the complete LangGraph StateGraph that wires ALL specialist agents
into one explicit pipeline with:
- Sequential flow: consent → resume → parallel → join → matching → interview → validation
- Conditional edges: validation pass/fail routing
- Self-healing back-edge: validation fail → diagnose → targeted agent → re-validate  (Lab 10)
- Escalation: retry budget exhaustion → assemble with warnings
- Budget enforcement at every node transition

Architecture:
    START → plan_workflow → lock_plan → consent_validation
        ├── consents missing → validation_agent (fails CONSENT_SATISFIED, escalates)
        └── resume_agent → [skill_gap_agent ‖ coding_analytics_agent]  (parallel fan-out, Lab 8)
            → join_parallel (merges consented GitHub skill evidence)
            → domain_specialists (Lab 13) → job_matching_agent → interview_agent → validation_agent
                ├── PASS → assemble_draft → END
                ├── FAIL + healable + retries left → diagnose_and_regenerate
                │       └── → (failing agent only) → ... → validation_agent  (Lab 10)
                └── FAIL otherwise → assemble_draft (marked failed) → END

All data access goes through the connector hub registered for the run (Lab 5).
The assembled draft is written to state["draft"] and is what the API persists,
re-validates on edit, and versions on approval (Lab 15).
"""
from typing import Dict, Any
from datetime import datetime, timezone
import logging

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import PlacementState, AuditEvent
from app.agents.coordinator import plan_workflow, lock_plan
from app.agents.resume_agent import resume_agent_node
from app.agents.skill_gap_agent import skill_gap_agent_node
from app.agents.coding_analytics_agent import coding_analytics_agent_node
from app.agents.job_matching_agent import job_matching_agent_node
from app.agents.interview_agent import interview_agent_node
from app.agents.validation_agent import validation_agent_node
from app.agents.domain_specialist_agent import domain_specialist_node
from app.agents.self_healing import (
    diagnose_and_regenerate as _diagnose_logic,
    regeneration_route,
    validation_route,
)
from app.core.runtime import runtime

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Infrastructure nodes (consent, join, diagnose, assemble)
# ---------------------------------------------------------------------------

def consent_validation_node(state: PlacementState) -> Dict[str, Any]:
    """
    Node: read the student's consent records from the Consent table (via the
    StudentConnector). Required sources must be
    `granted`; missing, revoked or invalid consent is never treated as granted.
    """
    from app.connectors.hub import HubUnavailableError, get_hub
    from app.services.consent import missing_required

    student_id = state.get("student_id", "")
    try:
        hub = get_hub(state)
        snapshot = hub.consent_status(student_id)
    except HubUnavailableError as exc:
        return {"consent_validated": False, "consent_status": None, "current_step": "consent_validation",
                "errors": [f"ConsentValidation: {exc}"]}
    except Exception as exc:
        return {"consent_validated": False, "consent_status": None, "current_step": "consent_validation",
                "errors": [f"ConsentValidation: could not read consent records ({exc.__class__.__name__})"]}

    missing = missing_required(snapshot)
    validated = not missing
    audit = AuditEvent(
        action="consent_validated" if validated else "consent_blocked",
        agent="ConsentValidation",
        timestamp=datetime.now(timezone.utc).isoformat(),
        details={"student_id": student_id, "status": {k: v["status"] for k, v in snapshot.items()},
                 "missing_required": missing},
    )
    update: Dict[str, Any] = {
        "consent_validated": validated,
        "consent_status": snapshot,
        "current_step": "consent_validation",
        "audit_events": [audit],
    }
    if not validated:
        update["errors"] = [f"ConsentValidation: required consent not granted — {missing}"]
    return update


def consent_router(state: PlacementState) -> str:
    return "granted" if state.get("consent_validated") else "blocked"


def join_parallel_node(state: PlacementState) -> Dict[str, Any]:
    """
    Node: join after the parallel Skill-Gap and Coding-Analytics branches.
    Skills corroborated by the student's consented GitHub repositories are merged
    into the gap report here, because the two branches run concurrently.
    """
    from app.agents.skill_gap_agent import apply_coding_evidence

    has_skill_gap = state.get("skill_gap_report") is not None
    has_coding = state.get("coding_analytics") is not None
    merge_status = {
        "skill_gap_report": "present" if has_skill_gap else "missing",
        "coding_analytics": "present" if has_coding else "missing",
    }
    errors = []
    if not has_skill_gap:
        errors.append("JoinParallel: skill_gap_report is missing")
    if not has_coding:
        errors.append("JoinParallel: coding_analytics is missing")

    result: Dict[str, Any] = {"current_step": "join_parallel"}
    updated = apply_coding_evidence(state) if (has_skill_gap and has_coding) else None
    if updated is not None:
        result["skill_gap_report"] = updated
        merge_status["github_skill_evidence"] = "merged"

    result["audit_events"] = [AuditEvent(
        action="parallel_results_merged", agent="JoinParallel",
        timestamp=datetime.now(timezone.utc).isoformat(), details=merge_status,
    )]
    if errors:
        result["errors"] = errors
    return result


def diagnose_and_regenerate_node(state: PlacementState) -> Dict[str, Any]:
    """
    Node: Delegate to the pure-Python self-healing logic (app.agents.self_healing).
    Reads diagnosis, picks healing target, writes it to state.
    """
    return _diagnose_logic(state)


DRAFT_SECTIONS = (
    "student_profile", "skill_gap_report", "coding_analytics", "specialist_analysis",
    "matching_result", "interview_result", "roadmap", "retrieval", "role_requirements", "student_context",
)


def assemble_draft_node(state: PlacementState) -> Dict[str, Any]:
    """
    Node: assemble the per-student readiness plan and shortlist draft.
    The draft is state-shaped (same section keys) so it can be re-validated after
    officer edits, and it is the object persisted, reviewed and versioned.
    """
    validation_passed = state.get("validation_passed", False)
    validation_report = state.get("validation_report") or {}
    plan = state.get("plan")
    draft: Dict[str, Any] = {
        "metadata": {
            "student_id": state.get("student_id"),
            "run_id": state.get("run_id"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "validation_status": "passed" if validation_passed else "failed",
            "validation_passed": validation_passed,
            "version": "draft",
            "extraction_method": (state.get("student_profile") or {}).get("extraction_method"),
        },
        "student_id": state.get("student_id"),
        "run_id": state.get("run_id"),
        "request": state.get("request_context"),
        "target_roles": state.get("target_roles") or [],
        "plan": plan.model_dump() if hasattr(plan, "model_dump") else plan,
        "consent_validated": state.get("consent_validated", False),
        "consent_status": state.get("consent_status"),
        "resume_data": {k: v for k, v in (state.get("resume_data") or {}).items()
                        if k in ("resume_id", "file_name", "is_duplicate", "similarity_score", "matched_student_id")},
        "evidence_records": state.get("evidence_records", []),
        "validation_report": validation_report,
        "officer_notes": [],
        "errors": state.get("errors", []),
    }
    for key in DRAFT_SECTIONS:
        draft[key] = state.get(key)
    draft["summary"] = {
        "readiness_percentage": ((state.get("matching_result") or {}).get("readiness_score") or {}).get("percentage"),
        "skill_coverage": (state.get("skill_gap_report") or {}).get("overall_coverage"),
        "target_roles": (state.get("skill_gap_report") or {}).get("target_roles", state.get("target_roles") or []),
        "top_matches": [
            {k: m.get(k) for k in ("company_name", "role_title", "match_percentage", "confidence", "is_eligible")}
            for m in ((state.get("matching_result") or {}).get("matches") or [])[:3]
        ],
        "evidence_count": len(state.get("evidence_records", [])),
        "checks_passed": validation_report.get("passed_checks", 0),
        "total_checks": validation_report.get("total_checks", 0),
    }
    if not validation_passed:
        draft["metadata"]["failing_checks"] = state.get("failing_checks", [])

    audit = AuditEvent(
        action="draft_assembled", agent="AssembleDraft", timestamp=datetime.now(timezone.utc).isoformat(),
        details={"validation_passed": validation_passed, "sections": [k for k in DRAFT_SECTIONS if draft.get(k)]},
    )
    return {"draft": draft, "current_step": "assemble_draft", "audit_events": [audit]}


# ---------------------------------------------------------------------------
# Router functions (conditional edges)
# ---------------------------------------------------------------------------

def coordinator_router(state: PlacementState) -> str:
    """Route from coordinator based on planning state."""
    next_node = state.get("next_node", END)
    if next_node == "end":
        return END
    return next_node


def validation_router(state: PlacementState) -> str:
    """
    Route from validation — delegates to self_healing.validation_route,
    but also checks the governed runtime budget.
    """
    if state.get("validation_passed", False):
        logger.info("[Router] Validation PASSED → assemble_draft")
        return "pass"

    # Check runtime budget (governed runtime check, only in graph context)
    is_safe, reason = runtime.enforce_state_budget(state)
    if not is_safe:
        logger.warning(f"[Router] Runtime budget exceeded: {reason} → escalating")
        return "fail_escalate"

    route = validation_route(state)
    logger.info(f"[Router] Validation FAILED → {route}")
    return route


def regeneration_router(state: PlacementState) -> str:
    """Route from diagnose_and_regenerate — delegates to self_healing.regeneration_route."""
    return regeneration_route(state)


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------

def build_placement_graph():
    """
    Build the complete Lab 7 agentic workflow graph.

    This is the full node graph with all specialist agents wired together:
    - Coordinator → Planning → Consent → Resume → Skill Gap → Coding Analytics
    - → Join → Job Matching → Interview → Validation
    - Validation → Pass/Fail routing → Assembly or Self-Healing loop
    """
    workflow = StateGraph(PlacementState)

    # =====================================================================
    # ADD ALL NODES
    # =====================================================================

    # Phase 1: Planning (from Lab 1)
    workflow.add_node("plan_workflow", plan_workflow)
    workflow.add_node("lock_plan", lock_plan)

    # Phase 2: Consent + Resume (from Labs 2-3)
    workflow.add_node("consent_validation", consent_validation_node)
    workflow.add_node("resume_agent", resume_agent_node)

    # Phase 3: Parallel agents (sequential in Lab 7, parallel in Lab 8)
    workflow.add_node("skill_gap_agent", skill_gap_agent_node)
    workflow.add_node("coding_analytics_agent", coding_analytics_agent_node)
    workflow.add_node("join_parallel", join_parallel_node)
    workflow.add_node("domain_specialists", domain_specialist_node)

    # Phase 4: Downstream agents
    workflow.add_node("job_matching_agent", job_matching_agent_node)
    workflow.add_node("interview_agent", interview_agent_node)

    # Phase 5: Validation + Assembly
    workflow.add_node("validation_agent", validation_agent_node)
    workflow.add_node("diagnose_and_regenerate", diagnose_and_regenerate_node)
    workflow.add_node("assemble_draft", assemble_draft_node)

    # =====================================================================
    # WIRE EDGES
    # =====================================================================

    # Entry point: Start with coordinator planning
    workflow.add_edge(START, "plan_workflow")

    # Coordinator routing: plan → lock → execute
    workflow.add_conditional_edges(
        "plan_workflow",
        coordinator_router,
        {
            "lock_plan": "lock_plan",
            "execute": "consent_validation",
            "consent_validation": "consent_validation",
            END: END,
        }
    )

    # Lock plan → consent validation
    workflow.add_edge("lock_plan", "consent_validation")

    # Consent → Resume (or straight to validation when required consent is missing)
    workflow.add_conditional_edges(
        "consent_validation",
        consent_router,
        {"granted": "resume_agent", "blocked": "validation_agent"},
    )

    # Phase 3: Parallel agents (true parallel fan-out for Lab 8)
    # Resume → Skill Gap AND Coding Analytics
    workflow.add_edge("resume_agent", "skill_gap_agent")
    workflow.add_edge("resume_agent", "coding_analytics_agent")

    # Both parallel agents → Join
    workflow.add_edge("skill_gap_agent", "join_parallel")
    workflow.add_edge("coding_analytics_agent", "join_parallel")

    # Join → Domain specialists (Lab 13) → Job Matching
    workflow.add_edge("join_parallel", "domain_specialists")
    workflow.add_edge("domain_specialists", "job_matching_agent")

    # Job Matching → Interview
    workflow.add_edge("job_matching_agent", "interview_agent")

    # Interview → Validation
    workflow.add_edge("interview_agent", "validation_agent")

    # Validation → Conditional routing
    workflow.add_conditional_edges(
        "validation_agent",
        validation_router,
        {
            "pass": "assemble_draft",
            "fail_retry": "diagnose_and_regenerate",
            "fail_escalate": "assemble_draft",
        }
    )

    # Self-healing loop: diagnose → targeted agent → validation
    # Lab 10: replace fixed edge with conditional dispatch to only the failing agent
    workflow.add_conditional_edges(
        "diagnose_and_regenerate",
        regeneration_router,
        {
            "skill_gap_agent": "skill_gap_agent",
            "coding_analytics_agent": "coding_analytics_agent",
            "job_matching_agent": "job_matching_agent",
            "interview_agent": "interview_agent",
            "validation_agent": "validation_agent",
        }
    )

    # Assembly → END
    workflow.add_edge("assemble_draft", END)

    # =====================================================================
    # COMPILE WITH CHECKPOINTING
    # =====================================================================
    compiled = workflow.compile(checkpointer=make_checkpointer())

    logger.info("[Graph] Full placement readiness graph compiled successfully.")
    return compiled


def make_checkpointer():
    """
    Lab 6: progress is saved after every node. With SQLite (default) the saved
    progress survives a crash or restart, so the run continues from the last
    completed step instead of starting over.
    """
    from app.config import settings
    if settings.CHECKPOINT_BACKEND.lower() == "memory":
        return MemorySaver()
    import os
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver
    path = settings.CHECKPOINT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    saver = SqliteSaver(sqlite3.connect(path, check_same_thread=False))
    saver.setup()
    return saver


# Export the compiled graph
agent_runner = build_placement_graph()
