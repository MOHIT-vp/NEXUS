"""
Skill Gap Agent (A2) — benchmarks the student's evidenced skills against verified
requirements for the roles *the student chose*.

Architecture contract:
- Input: student_profile, target_roles (from the clarified request)
- Data: RoleConnector (benchmark library + job-listing requirements) and the
  KnowledgeConnector (role guides, learning resources) — through the hub only
- Output: per-role coverage, strengths, gaps (required vs preferred), each gap
  citing its requirement source and an actionable, resource-backed recommendation
- Guardrails: use approved benchmarks/verified listings only; cite the source of
  each; never label a student "unfit"; never invent requirements
- LLM: optional narration of the summary only; numbers are deterministic
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import logging

from app.agents.llm import get_chat_model
from app.agents.state import AuditEvent, PlacementState
from app.connectors.hub import HubUnavailableError, get_hub
from app.core.skills import GITHUB_LANGUAGE_SKILLS, canonical, display_name
from app.schemas.evidence import EvidenceRecord

logger = logging.getLogger(__name__)

PROFICIENCY_LEVELS = {"beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4}

SEVERITY_MAP = {0: "none", 1: "low", 2: "medium", 3: "high", 4: "critical"}

IMPORTANCE_WEIGHT = {"required": 1.0, "preferred": 0.5, "nice_to_have": 0.5}


def _proficiency_to_int(level: Optional[str]) -> int:
    return PROFICIENCY_LEVELS.get((level or "").lower().strip(), 0)


# A gap in a skill the role only PREFERS is less urgent than one it requires
_PREFERRED_SEVERITY = {"critical": "medium", "high": "medium", "medium": "low", "low": "low", "none": "none"}


def _compute_gap_severity(required_level: str, current_level: Optional[str], importance: str = "required") -> str:
    """Missing required skill → critical; otherwise the number of levels below the
    requirement. Preferred / nice-to-have skills are capped at medium."""
    if not current_level:
        severity = "critical"
    else:
        delta = max(0, _proficiency_to_int(required_level) - _proficiency_to_int(current_level))
        severity = SEVERITY_MAP.get(delta, "critical")
    return severity if importance == "required" else _PREFERRED_SEVERITY.get(severity, severity)


def _best_levels(student_skills: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for s in student_skills or []:
        key = canonical(s.get("name", ""))
        if not key:
            continue
        prev = out.get(key)
        if prev is None or _proficiency_to_int(s.get("proficiency")) > _proficiency_to_int(prev.get("proficiency")):
            out[key] = s
    return out


def _compute_skill_coverage(
    student_skills: List[Dict[str, Any]],
    required_skills: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Deterministic coverage. Required requirements weigh 1.0, preferred 0.5.
    Returns overall_coverage (0-100), strengths, gaps, total_required, matched.
    """
    if not required_skills:
        return {"overall_coverage": 0.0, "strengths": [], "gaps": [], "total_required": 0, "matched": 0,
                "required_coverage": 0.0}

    levels = _best_levels(student_skills)
    strengths, gaps = [], []
    matched = 0
    weight_total = weight_matched = 0.0
    req_total = req_matched = 0

    for req in required_skills:
        name = req.get("skill_name", req.get("name", "")).strip()
        key = canonical(name)
        req_level = req.get("expected_level", req.get("min_proficiency", "intermediate"))
        importance = req.get("importance", "required")
        source = req.get("source", "unspecified source")
        w = IMPORTANCE_WEIGHT.get(importance, 1.0)
        weight_total += w
        if importance == "required":
            req_total += 1

        have = levels.get(key)
        current = have.get("proficiency") if have else None
        severity = _compute_gap_severity(req_level, current, importance)
        display = display_name(key) if key else name

        if severity == "none":
            matched += 1
            weight_matched += w
            if importance == "required":
                req_matched += 1
            strengths.append({
                "skill": display,
                "level": current,
                "importance": importance,
                "evidence": (have.get("evidence") or [f"Listed as {current}"])[:3] if have else [],
                "verified_by": sorted(set(have.get("verified_by") or [have.get("source", "resume")])) if have else [],
                "benchmark_source": source,
            })
        else:
            gaps.append({
                "skill": display,
                "required_level": req_level,
                "current_level": current or "missing",
                "severity": severity,
                "importance": importance,
                "benchmark_source": source,
                "rationale": req.get("rationale"),
            })

    return {
        "overall_coverage": round(weight_matched / weight_total * 100, 1) if weight_total else 0.0,
        "required_coverage": round(req_matched / req_total * 100, 1) if req_total else 100.0,
        "strengths": strengths,
        "gaps": gaps,
        "total_required": len(required_skills),
        "matched": matched,
    }


def _assessment_label(coverage: float) -> str:
    # Never "unfit" — developmental labels only (guardrail)
    if coverage >= 80:
        return "strong_candidate"
    if coverage >= 60:
        return "competitive"
    if coverage >= 40:
        return "developing"
    return "early_stage"


def _recommendation(gap: Dict[str, Any], role_title: str, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
    skill = gap["skill"]
    current = gap["current_level"]
    need = gap["required_level"]
    have = "no evidence of this skill was found" if current == "missing" else f"your evidence shows {current} level"
    lead = (f"{skill}: {have}; {role_title} {'requires' if gap['importance'] == 'required' else 'prefers'} "
            f"{need} level (source: {gap['benchmark_source']}).")
    if resources:
        r = resources[0]
        action = (f"Work through \"{r['title']}\"{' (' + r['url'] + ')' if r.get('url') else ''}, then build or "
                  f"extend a project that uses {skill} and add it to your resume/GitHub so the evidence is verifiable.")
    else:
        action = (f"No curated {skill} resource is in the knowledge base yet; ask the Placement Cell for one, and "
                  f"demonstrate {skill} in a project so it can be verified.")
    return {
        "recommendation": f"{lead} {action}",
        "explanation": f"Gap of severity '{gap['severity']}' between current ({current}) and required ({need}) level.",
        "resources": [{"title": r["title"], "url": r.get("url"), "source": r["source"]} for r in resources[:2]],
    }


def _github_skill_evidence(coding_analytics: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Skills evidenced by the student's own consented coding platforms:
    - GitHub: primary languages of original public repositories;
    - LeetCode: solved-problem volume evidences Data Structures and Algorithms.
    """
    if not coding_analytics:
        return []
    out = []
    sources = {s.get("source"): s for s in coding_analytics.get("sources", []) if s.get("status") == "ok" and s.get("data")}
    gh = sources.get("github")
    if gh:
        for lang, repo_count in (gh["data"].get("languages") or {}).items():
            key = GITHUB_LANGUAGE_SKILLS.get(lang)
            if not key:
                continue
            out.append({
                "name": display_name(key),
                "proficiency": "intermediate" if repo_count >= 3 else "beginner",
                "source": "github",
                "verified_by": ["github"],
                "evidence": [f"GitHub: {repo_count} original public repo(s) with {lang} as the primary language"],
            })
    lc = sources.get("leetcode")
    if lc:
        d = lc["data"]
        solved = d.get("total_solved", 0) or 0
        hard = (d.get("difficulty_distribution") or {}).get("hard", 0) or 0
        level = None
        if solved >= 300 and hard >= 30:
            level = "advanced"
        elif solved >= 150:
            level = "intermediate"
        elif solved >= 50:
            level = "beginner"
        if level:
            for skill in ("Data Structures", "Algorithms"):
                out.append({
                    "name": skill, "proficiency": level, "source": "leetcode", "verified_by": ["leetcode"],
                    "evidence": [f"LeetCode: {solved} problems solved ({hard} hard)"],
                })
    return out


def merge_skill_evidence(profile_skills: List[Dict[str, Any]], extra: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Combine resume skills with skills corroborated by other consented sources."""
    merged: Dict[str, Dict[str, Any]] = {}
    for s in profile_skills or []:
        key = canonical(s.get("name", ""))
        if key:
            merged[key] = {**s, "verified_by": sorted(set(s.get("verified_by") or [s.get("source", "resume")]))}
    for s in extra:
        key = canonical(s["name"])
        if key in merged:
            cur = merged[key]
            cur["verified_by"] = sorted(set(cur.get("verified_by", [])) | set(s.get("verified_by", [])))
            cur["evidence"] = list(cur.get("evidence") or []) + s["evidence"]
            if _proficiency_to_int(s["proficiency"]) > _proficiency_to_int(cur.get("proficiency")):
                cur["proficiency"] = s["proficiency"]
        else:
            merged[key] = dict(s)
    return list(merged.values())


def build_skill_gap_report(
    student_profile: Dict[str, Any],
    role_requirements: List[Dict[str, Any]],
    resources_by_skill: Dict[str, List[Dict[str, Any]]],
    extra_skill_evidence: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Pure function: compute the per-role and aggregate gap report."""
    skills = merge_skill_evidence(student_profile.get("skills", []), extra_skill_evidence or [])
    per_role = []
    union_gaps: Dict[str, Dict[str, Any]] = {}
    union_strengths: Dict[str, Dict[str, Any]] = {}

    for role in role_requirements:
        cov = _compute_skill_coverage(skills, role.get("requirements", []))
        for g in cov["gaps"]:
            g.update(_recommendation(g, role["title"], resources_by_skill.get(canonical(g["skill"]), [])))
            g["roles"] = [role["title"]]
            key = canonical(g["skill"])
            if key in union_gaps:
                existing = union_gaps[key]
                existing["roles"] = sorted(set(existing["roles"]) | {role["title"]})
                if PROFICIENCY_LEVELS.get(g["required_level"], 0) > PROFICIENCY_LEVELS.get(existing["required_level"], 0):
                    existing.update({k: g[k] for k in ("required_level", "severity", "recommendation", "benchmark_source")})
                if g["importance"] == "required":
                    existing["importance"] = "required"
            else:
                union_gaps[key] = dict(g)
        for s in cov["strengths"]:
            union_strengths.setdefault(canonical(s["skill"]), s)
        per_role.append({
            "role_key": role.get("role_key"),
            "title": role["title"],
            "requirement_status": role.get("status"),
            "coverage": cov["overall_coverage"],
            "required_coverage": cov.get("required_coverage"),
            "assessment": _assessment_label(cov["overall_coverage"]) if role.get("requirements") else "no_verified_requirements",
            "requirements_count": len(role.get("requirements", [])),
            "requirement_sources": sorted({r.get("source") for r in role.get("requirements", []) if r.get("source")}),
            "gaps_count": len(cov["gaps"]),
            "strengths_count": len(cov["strengths"]),
        })

    roles_with_reqs = [r for r in per_role if r["requirements_count"]]
    overall = round(sum(r["coverage"] for r in roles_with_reqs) / len(roles_with_reqs), 1) if roles_with_reqs else 0.0
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    gaps = sorted(union_gaps.values(), key=lambda g: (g["importance"] != "required", severity_order.get(g["severity"], 9)))

    return {
        "overall_coverage": overall,
        "overall_assessment": _assessment_label(overall) if roles_with_reqs else "no_verified_requirements",
        "per_role": per_role,
        "strengths": list(union_strengths.values()),
        "gaps": gaps,
        "required_gaps": [g for g in gaps if g["importance"] == "required"],
        "preferred_gaps": [g for g in gaps if g["importance"] != "required"],
        "total_required_skills": sum(r["requirements_count"] for r in per_role),
        "matched_skills": len(union_strengths),
        "target_roles": [r["title"] for r in per_role],
        "skills_considered": [{"name": s["name"], "proficiency": s.get("proficiency"),
                               "verified_by": s.get("verified_by", [])} for s in skills],
        "citation": "; ".join(sorted({src for r in per_role for src in r["requirement_sources"]})) or None,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def _gap_resources(hub, role_requirements: List[Dict[str, Any]], student_skills: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Retrieve learning resources for each potential gap skill and role guides for each role."""
    levels = _best_levels(student_skills)
    gap_skills: List[str] = []
    for role in role_requirements:
        for req in role.get("requirements", []):
            key = canonical(req["skill_name"])
            have = levels.get(key)
            if (not have or _compute_gap_severity(req.get("expected_level", "intermediate"), have.get("proficiency")) != "none") \
                    and key not in gap_skills:
                gap_skills.append(key)

    resources: Dict[str, List[Dict[str, Any]]] = {}
    statuses = []
    for key in gap_skills[:15]:
        res = hub.retrieve(f"{display_name(key)} learning resource", doc_types=["learning_resource"], k=3)
        statuses.append(res.status)
        hits, seen_urls = [], set()
        for i in res.items:
            if not (key in [canonical(t) for t in i.tags] or i.title.lower().startswith(display_name(key).lower() + ":")):
                continue
            if i.url and i.url in seen_urls:
                continue
            seen_urls.add(i.url)
            hits.append(i.model_dump())
        if hits:
            resources[key] = hits

    role_guides = []
    for role in role_requirements:
        res = hub.retrieve(f"{role['title']} required skills", role_families=[role["role_key"]] if role.get("role_key") else None,
                           doc_types=["role_guide", "job_description"], k=3)
        statuses.append(res.status)
        role_guides.append({"role": role["title"], "status": res.status, "error": res.error,
                            "items": [i.model_dump() for i in res.items]})

    overall = "ok" if "ok" in statuses else ("unavailable" if "unavailable" in statuses else "empty")
    return {"resources_by_skill": resources, "role_guides": role_guides, "status": overall}


def skill_gap_agent_node(state: PlacementState) -> Dict[str, Any]:
    """LangGraph node: Skill Gap Agent."""
    profile = state.get("student_profile")
    if not profile:
        return {"errors": ["SkillGapAgent: No student profile available in state."]}

    target_roles = [r for r in (state.get("target_roles") or []) if r]
    if not target_roles:
        return {"errors": ["SkillGapAgent: no target roles were provided; the planner must clarify them first."]}

    try:
        hub = get_hub(state)
        role_requirements = hub.role_requirements(target_roles)
        retrieval = _gap_resources(hub, role_requirements, profile.get("skills", []))
        # Lab 4 history retrieval: anonymised prior students with a similar profile
        from app.services.similarity import profile_text
        similar = hub.similar_prior_students(
            state.get("student_id") or "",
            profile_text([s.get("name", "") for s in profile.get("skills", [])], [r["title"] for r in role_requirements]),
            k=5) if hasattr(hub, "similar_prior_students") else []
    except HubUnavailableError as exc:
        return {"errors": [f"SkillGapAgent: {exc}"]}

    report = build_skill_gap_report(profile, role_requirements, retrieval["resources_by_skill"])

    missing = [r["title"] for r in role_requirements if r["status"] != "ok"]
    if missing:
        report["unverified_roles"] = missing

    summary = (f"Evidence-backed coverage of {report['overall_coverage']}% across {len(report['per_role'])} target role(s); "
               f"{len(report['required_gaps'])} required and {len(report['preferred_gaps'])} preferred skill gaps.")
    narration_method = "deterministic"
    llm = get_chat_model(temperature=0.2)
    if llm is not None:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            msg = llm.invoke([
                SystemMessage(content=(
                    "You summarise a pre-computed skill-gap report in 2-3 sentences for a student. "
                    "Use ONLY the numbers and skill names given. Never call the student unfit. Do not add skills.")),
                HumanMessage(content=f"Report: coverage={report['overall_coverage']}, roles={report['target_roles']}, "
                                     f"required_gaps={[g['skill'] for g in report['required_gaps']]}, "
                                     f"strengths={[s['skill'] for s in report['strengths']]}"),
            ])
            text = getattr(msg, "content", "")
            if isinstance(text, str) and text.strip():
                summary = "[AI-generated summary] " + text.strip()[:800]
                narration_method = "llm"
        except Exception as exc:
            logger.warning(f"[SkillGapAgent] narration unavailable: {exc}")
    report["summary"] = summary
    report["narration_method"] = narration_method
    report["strength_highlights"] = [s["skill"] for s in report["strengths"][:5]]

    evidence = [EvidenceRecord(
        entity_type="skill_gap_report",
        evidence_type="benchmark_comparison",
        source=report["citation"] or "no verified requirement source",
        content=(f"Coverage {report['overall_coverage']}% vs verified requirements for {report['target_roles']}; "
                 f"{len(report['gaps'])} gaps, {len(report['strengths'])} strengths."),
        scope_tags=["skill_gap", "benchmarks"],
    ).model_dump()]
    for g in report["gaps"][:20]:
        evidence.append(EvidenceRecord(
            entity_type="skill_gap_item", evidence_type="requirement_citation", source=g["benchmark_source"],
            content=f"{g['skill']}: required {g['required_level']} ({g['importance']}), current {g['current_level']}.",
            scope_tags=["skill_gap", canonical(g["skill"])],
        ).model_dump())

    if similar:
        evidence.append(EvidenceRecord(
            entity_type="similar_students", evidence_type="history_retrieval", source="Published plans of prior students (anonymised)",
            content=f"{len(similar)} prior students with similar profiles; top similarity {similar[0]['similarity']}.",
            scope_tags=["retrieval", "similarity", "history"],
        ).model_dump())

    audit = AuditEvent(action="skill_gap_analyzed", agent="SkillGapAgent",
                       timestamp=datetime.now(timezone.utc).isoformat(),
                       details={"coverage": report["overall_coverage"], "roles": report["target_roles"],
                                "gaps": len(report["gaps"]), "unverified_roles": missing,
                                "retrieval_status": retrieval["status"], "similar_prior_students": len(similar)})

    return {
        "skill_gap_report": report,
        "role_requirements": role_requirements,
        "retrieval": {
            "status": retrieval["status"],
            "role_guides": retrieval["role_guides"],
            "learning_resources": retrieval["resources_by_skill"],
            "similar_prior_students": similar,
        },
        "evidence_records": evidence,
        "audit_events": [audit],
    }


def apply_coding_evidence(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Called at the join point (after both parallel branches finish): recompute the
    report with skills corroborated by the student's consented GitHub data.
    """
    report = state.get("skill_gap_report")
    reqs = state.get("role_requirements")
    profile = state.get("student_profile")
    extra = _github_skill_evidence(state.get("coding_analytics"))
    if not report or not reqs or not profile or not extra:
        return None
    resources = (state.get("retrieval") or {}).get("learning_resources", {})
    updated = build_skill_gap_report(profile, reqs, resources, extra)
    for k in ("summary", "narration_method", "unverified_roles"):
        if k in report:
            updated[k] = report[k]
    updated["strength_highlights"] = [s["skill"] for s in updated["strengths"][:5]]
    updated["corroborated_by"] = sorted({v for e in extra for v in e.get("verified_by", [])})
    return updated
