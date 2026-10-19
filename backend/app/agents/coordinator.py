"""
apniLeap AURA Coordinator — builds and locks the run plan before work begins.

The plan is derived from the clarified request (Lab 1 planner session): target
roles, timeline and priorities. An LLM may phrase the goal summary when one is
configured; the step list itself is fixed by the governed pipeline.
"""
from datetime import datetime, timezone
from typing import Any, Dict

from app.agents.llm import get_chat_model
from app.agents.state import AuditEvent, ExecutionPlan, ExecutionStep, PlacementState

PIPELINE_STEPS = [
    ("ConsentValidation", "Read source-specific consent records; stop if required consent is missing", []),
    ("ResumeAgent", "Parse the student's own uploaded resume into an evidenced profile", ["1"]),
    ("SkillGapAgent", "Benchmark skills against verified requirements for the target roles", ["2"]),
    ("CodingAnalyticsAgent", "Aggregate consented GitHub/LeetCode activity", ["2"]),
    ("DomainSpecialists", "Apply the domain specialist packs for the student's goals", ["3", "4"]),
    ("JobMatchingAgent", "Score and rank open listings from the placement database", ["5"]),
    ("InterviewAgent", "Build the mock-interview plan and learning roadmap", ["6"]),
    ("ValidationAgent", "Run the acceptance checks (hard gate)", ["7"]),
]


def build_plan(state: PlacementState) -> ExecutionPlan:
    request = state.get("request_context") or {}
    roles = state.get("target_roles") or []
    timeline = request.get("timeline") if isinstance(request, dict) else None
    priorities = request.get("priorities") if isinstance(request, dict) else None
    goal = f"Readiness plan and shortlist for target role(s): {', '.join(roles) or 'unspecified'}"
    if timeline:
        goal += f"; timeline {timeline}"
    if priorities:
        goal += f"; priorities {', '.join(priorities)}"
    return ExecutionPlan(
        goal_summary=goal,
        steps=[ExecutionStep(step_id=str(i + 1), agent=a, description=d, requires_input_from=deps)
               for i, (a, d, deps) in enumerate(PIPELINE_STEPS)],
    )


def plan_workflow(state: PlacementState) -> Dict[str, Any]:
    """Node: create the execution plan (a locked plan is never modified)."""
    if state.get("plan_locked", False):
        return {"current_step": "plan_workflow", "next_node": "execute"}

    plan = build_plan(state)
    method = "deterministic"
    llm = get_chat_model(temperature=0.1)
    if llm is not None:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            msg = llm.invoke([
                SystemMessage(content="Rewrite this goal as one clear sentence. Do not add roles or facts."),
                HumanMessage(content=plan.goal_summary),
            ])
            text = getattr(msg, "content", "")
            if isinstance(text, str) and 10 < len(text.strip()) < 400:
                plan.goal_summary = text.strip()
                method = "llm_phrased"
        except Exception:
            pass

    audit = AuditEvent(action="plan_generated", agent="Coordinator", timestamp=datetime.now(timezone.utc).isoformat(),
                       details={"steps_count": len(plan.steps), "method": method, "goal": plan.goal_summary})
    return {"plan": plan, "audit_events": [audit], "current_step": "plan_workflow", "next_node": "lock_plan"}


def lock_plan(state: PlacementState) -> Dict[str, Any]:
    """Node: lock the plan before execution; a locked plan cannot be mutated."""
    plan = state.get("plan")
    if not plan:
        return {"errors": ["Attempted to lock an empty plan"], "next_node": "end"}
    plan.is_locked = True
    audit = AuditEvent(action="plan_locked", agent="Coordinator", timestamp=datetime.now(timezone.utc).isoformat(),
                       details={"locked": True})
    return {"plan": plan, "plan_locked": True, "audit_events": [audit], "current_step": "lock_plan",
            "next_node": "consent_validation"}
