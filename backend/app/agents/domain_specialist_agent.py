"""
Domain Specialist node (Lab 13) — selects the specialists for the student's goals
and merges their validated analysis into the plan.

Selection order: specialists of the resolved target roles, then any preferred
domains the student stated, then (only if nothing else resolved) the department.
Multiple specialists are supported; the primary one's scoring weights dominate.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List

from pydantic import ValidationError

from app.agents.state import AuditEvent, PlacementState
from app.core.domains.specialists import combined_weights, run_specialist
from app.core.roles import DOMAIN_LABELS, domains_for, resolve_targets
from app.schemas.evidence import EvidenceRecord

DEPARTMENT_HINTS = {
    "computer": "software", "information technology": "software", "it": "software", "cse": "software",
    "data": "analytics", "ai": "analytics",
    "mechanical": "core", "civil": "core", "electrical": "core", "electronics": "core", "ece": "core", "eee": "core",
    "chemical": "core", "production": "core",
}


def select_domains(state: Dict[str, Any]) -> List[Dict[str, str]]:
    ctx = state.get("student_context") or {}
    prefs = ctx.get("career_preferences") or {}
    targets = resolve_targets(state.get("target_roles") or [])
    domains = domains_for(targets, prefs.get("preferred_domains"))
    reasons = {}
    for t in targets:
        for d in t["domains"]:
            reasons.setdefault(d, f"Target role: {t['title']}")
    for d in prefs.get("preferred_domains") or []:
        reasons.setdefault(d, "Stated preferred domain")
    if not domains:
        dept = (ctx.get("department") or "").lower()
        for hint, d in DEPARTMENT_HINTS.items():
            if hint and hint in dept.split() or (len(hint) > 3 and hint in dept):
                domains = [d]
                reasons[d] = f"Department: {ctx.get('department')}"
                break
    return [{"domain": d, "reason": reasons.get(d, "Selected")} for d in domains if d in DOMAIN_LABELS]


def domain_specialist_node(state: PlacementState) -> Dict[str, Any]:
    selected = select_domains(state)
    outputs, rejected = [], []
    for sel in selected:
        try:
            outputs.append(run_specialist(sel["domain"], state, sel["reason"]))
        except (ValidationError, ValueError, KeyError) as exc:
            rejected.append({"domain": sel["domain"], "error": str(exc)[:300]})

    analysis = {
        "selected_domains": [s["domain"] for s in selected],
        "specialists": [o.model_dump() for o in outputs],
        "rejected_outputs": rejected,
        "scoring_weights": combined_weights(outputs),
        "status": "ok" if outputs else ("no_domain_selected" if not selected else "all_rejected"),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    evidence = [EvidenceRecord(
        entity_type="specialist_analysis", evidence_type="domain_pack",
        source=f"Domain pack: {o.name}",
        content=f"{o.name}: coverage {o.domain_coverage}% of domain focus skills; {len(o.recommendations)} recommendations ({o.relevance}).",
        scope_tags=["specialist", o.domain],
    ).model_dump() for o in outputs]
    audit = AuditEvent(action="domain_specialists_applied", agent="DomainSpecialists",
                       timestamp=datetime.now(timezone.utc).isoformat(),
                       details={"selected": analysis["selected_domains"], "rejected": rejected})
    return {"specialist_analysis": analysis, "evidence_records": evidence, "audit_events": [audit],
            "current_step": "domain_specialists"}
