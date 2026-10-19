"""
Job Matching Agent (A4) — placement score + ranked company/role matches.

Architecture contract:
- Input: evidenced profile, skill-gap report, coding analytics, specialist weights
- Data: JobConnector via the hub — active listings from the companies/jobs tables
- Scoring: 100% deterministic; the LLM may only add a labelled narrative
- Guardrails: show confidence and reasoning; do not overstate fit; route
  low-confidence and stale/unverified matches to human review; enforce
  eligibility (CGPA / backlogs / experience); never submit applications
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import logging

from app.agents.llm import get_chat_model
from app.agents.state import AuditEvent, PlacementState
from app.connectors.hub import HubUnavailableError, get_hub
from app.core.roles import resolve_targets
from app.core.skills import canonical, canonical_set
from app.schemas.evidence import EvidenceRecord

logger = logging.getLogger(__name__)

DEFAULT_SCORING_CONFIG = {
    "skill_coverage": {"weight": 0.40, "max_points": 40},
    "coding_performance": {"weight": 0.25, "max_points": 25},
    "project_relevance": {"weight": 0.15, "max_points": 15},
    "interview_readiness": {"weight": 0.15, "max_points": 15},
    "eligibility": {"weight": 0.05, "max_points": 5},
}

LOW_CONFIDENCE_THRESHOLD = 0.6

APPLICATION_POLICY = ("The portal never submits applications. Students apply themselves through the "
                      "company's application link after the Placement Cell releases the plan.")


def scoring_config_from_weights(weights: Optional[Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    """Build the scoring config from Lab 13 specialist weights (falls back to the default)."""
    if not weights:
        return {k: dict(v) for k, v in DEFAULT_SCORING_CONFIG.items()}
    mapping = {
        "skill_coverage": weights.get("skill_coverage", 0.4),
        "coding_performance": weights.get("coding_performance", 0.25),
        "project_relevance": weights.get("project_relevance", 0.15),
        "interview_readiness": weights.get("interview_performance", 0.15),
        "eligibility": weights.get("eligibility", 0.05),
    }
    total = sum(mapping.values()) or 1.0
    return {k: {"weight": round(v / total, 4), "max_points": round(v / total * 100, 2)} for k, v in mapping.items()}


# ---------------------------------------------------------------------------
# Deterministic scoring functions
# ---------------------------------------------------------------------------

def _compute_skill_coverage_score(
    student_skills: List[Dict[str, Any]],
    required_skills: List[str],
    preferred_skills: List[str],
    max_points: float,
) -> Tuple[float, Dict[str, Any]]:
    """Required skills give 85% of the points, preferred skills the remaining 15%."""
    have = canonical_set(student_skills)
    if not required_skills and not preferred_skills:
        return 0.0, {"matched_required": 0, "total_required": 0, "required_ratio": 0.0,
                     "note": "Listing has no skill requirements recorded"}
    req_matches = sum(1 for s in required_skills if canonical(s) in have)
    req_ratio = req_matches / len(required_skills) if required_skills else 1.0
    pref_matches = sum(1 for s in preferred_skills if canonical(s) in have) if preferred_skills else 0
    pref_ratio = pref_matches / len(preferred_skills) if preferred_skills else 0.0
    score = round(min(req_ratio * max_points * 0.85 + pref_ratio * max_points * 0.15, max_points), 2)
    return score, {
        "matched_required": req_matches,
        "total_required": len(required_skills),
        "matched_preferred": pref_matches,
        "total_preferred": len(preferred_skills),
        "required_ratio": round(req_ratio, 2),
    }


def coding_available(coding_analytics: Optional[Dict[str, Any]]) -> bool:
    if not coding_analytics:
        return False
    summary = coding_analytics.get("summary") or {}
    if "data_available" in summary:
        return bool(summary["data_available"])
    return any(k in summary for k in ("coding_percentile", "coding_index", "total_solved"))


def _compute_coding_performance_score(
    coding_analytics: Optional[Dict[str, Any]],
    max_points: float,
) -> Tuple[float, Dict[str, Any]]:
    """Uses the coding index (LeetCode) or GitHub activity; 0 with a reason when unavailable."""
    if not coding_available(coding_analytics):
        return 0.0, {"reason": "No consented coding-platform data available", "available": False}
    summary = coding_analytics.get("summary", {})
    index = summary.get("coding_index", summary.get("coding_percentile"))
    trend = summary.get("activity_trend", "stable")
    trend_bonus = max_points * {"improving": 0.10, "stable": 0.0, "declining": -0.05}.get(trend, 0)
    if index is not None:
        difficulty = summary.get("difficulty_score", 0) or 0
        base = (index / 100) * max_points * 0.7
        diff_bonus = (difficulty / 100) * max_points * 0.2
        score = round(min(max(base + diff_bonus + trend_bonus, 0), max_points), 2)
        return score, {"basis": "leetcode", "coding_index": index, "difficulty_score": difficulty,
                       "trend": trend, "available": True}
    gh = summary.get("github") or {}
    activity = min(gh.get("recently_active_repos", 0) / 5, 1.0)
    breadth = min(gh.get("original_repos", 0) / 10, 1.0)
    score = round(min(max((activity * 0.5 + breadth * 0.5) * max_points * 0.8 + trend_bonus, 0), max_points), 2)
    return score, {"basis": "github", "recently_active_repos": gh.get("recently_active_repos", 0),
                   "original_repos": gh.get("original_repos", 0), "trend": trend, "available": True}


def _compute_project_relevance_score(
    student_profile: Dict[str, Any],
    job: Dict[str, Any],
    max_points: float,
) -> Tuple[float, Dict[str, Any]]:
    projects = student_profile.get("projects", [])
    if not projects:
        return 0.0, {"reason": "No projects found"}
    relevant = {canonical(s) for s in job.get("required_skills", []) + job.get("preferred_skills", [])}
    if not relevant:
        return 0.0, {"reason": "Listing has no skill requirements recorded"}
    matching_projects = 0
    total_matches = 0
    for p in projects:
        overlap = canonical_set(p.get("technologies", [])) & relevant
        if overlap:
            matching_projects += 1
            total_matches += len(overlap)
    ratio = matching_projects / len(projects)
    depth = min(total_matches / max(len(relevant), 1), 1.0)
    return round((ratio * 0.6 + depth * 0.4) * max_points, 2), {
        "matching_projects": matching_projects,
        "total_projects": len(projects),
        "tech_overlap_count": total_matches,
    }


def _check_eligibility(
    student_profile: Dict[str, Any],
    job: Dict[str, Any],
    max_points: float,
    academic: Optional[Dict[str, Any]] = None,
) -> Tuple[float, bool, Dict[str, Any]]:
    """
    Binary eligibility. CGPA comes from consented academic records first, then the
    resume. If a listing has a CGPA cutoff and no CGPA is available, eligibility
    cannot be verified and the match is treated as not eligible.
    """
    academic = academic or {}
    education = student_profile.get("education") or {}
    gpa = academic.get("cgpa") if academic.get("cgpa") is not None else education.get("gpa")
    gpa_source = "academic_records" if academic.get("cgpa") is not None else ("resume" if gpa is not None else None)
    backlogs = academic.get("active_backlogs")
    min_cgpa = float(job.get("min_cgpa") or 0)
    max_backlogs = job.get("max_backlogs")
    min_exp = job.get("min_experience") or 0

    reasons, eligible, verified = [], True, True
    if min_cgpa > 0:
        if gpa is None:
            eligible, verified = False, False
            reasons.append(f"CGPA cutoff {min_cgpa} cannot be verified: no CGPA in consented academic records or resume")
        elif float(gpa) < min_cgpa:
            eligible = False
            reasons.append(f"CGPA {gpa} below minimum {min_cgpa}")
    if max_backlogs is not None and backlogs is not None and backlogs > max_backlogs:
        eligible = False
        reasons.append(f"{backlogs} active backlog(s) exceed the allowed {max_backlogs}")
    years = student_profile.get("years_experience", 0) or 0
    if min_exp and years < min_exp:
        eligible = False
        reasons.append(f"Experience {years}y below minimum {min_exp}y")

    return (max_points if eligible else 0.0), eligible, {
        "is_eligible": eligible,
        "verified": verified,
        "student_gpa": gpa,
        "gpa_source": gpa_source,
        "required_gpa": min_cgpa,
        "active_backlogs": backlogs,
        "max_backlogs": max_backlogs,
        "fail_reasons": reasons,
    }


def _compute_match_confidence(skill_score, coding_score, eligibility, skill_details, config,
                              coding_ok: bool = True, stale: bool = False) -> float:
    """0-1 confidence; low when ineligible, few data points, low required coverage or stale listing."""
    if not eligibility:
        return 0.1
    factors = [skill_details.get("required_ratio", 0), 1.0 if coding_ok else 0.3]
    skill_max = config["skill_coverage"]["max_points"]
    coding_max = config["coding_performance"]["max_points"] if coding_ok else 0
    denom = (skill_max + coding_max) * 0.65 or 1
    factors.append(min((skill_score + (coding_score if coding_ok else 0)) / denom, 1.0))
    conf = sum(factors) / len(factors)
    if stale:
        conf *= 0.8
    return round(min(max(conf, 0.0), 1.0), 2)


def _target_match(job: Dict[str, Any], targets: List[Dict[str, Any]]) -> Optional[str]:
    title = (job.get("role_title") or "").lower()
    family = (job.get("role_family") or "").lower()
    for t in targets:
        if family and family in [f.lower() for f in t.get("job_families", [])]:
            return t["title"]
        if t["title"].lower() in title or title in t["title"].lower():
            return t["title"]
    return None


def _score_single_job(
    student_profile: Dict[str, Any],
    coding_analytics: Optional[Dict[str, Any]],
    job: Dict[str, Any],
    config: Dict[str, Any],
    academic: Optional[Dict[str, Any]] = None,
    targets: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    coding_ok = coding_available(coding_analytics)
    skill_score, skill_details = _compute_skill_coverage_score(
        student_profile.get("skills", []), job.get("required_skills", []), job.get("preferred_skills", []),
        config["skill_coverage"]["max_points"])
    coding_score, coding_details = _compute_coding_performance_score(coding_analytics, config["coding_performance"]["max_points"])
    project_score, project_details = _compute_project_relevance_score(student_profile, job, config["project_relevance"]["max_points"])
    elig_score, is_eligible, elig_details = _check_eligibility(student_profile, job, config["eligibility"]["max_points"], academic)

    # Interview performance is unknown until a supervised mock interview is graded:
    # the component is excluded (not guessed) and the total is rescaled.
    excluded = ["interview_readiness"] + ([] if coding_ok else ["coding_performance"])
    breakdown = [
        {"component": "skill_coverage", "points": skill_score, "max": config["skill_coverage"]["max_points"], "details": skill_details},
        {"component": "coding_performance", "points": coding_score, "max": config["coding_performance"]["max_points"],
         "details": coding_details, "excluded": not coding_ok},
        {"component": "project_relevance", "points": project_score, "max": config["project_relevance"]["max_points"], "details": project_details},
        {"component": "interview_readiness", "points": 0.0, "max": config["interview_readiness"]["max_points"],
         "details": {"status": "not_assessed", "note": "Excluded until a graded mock interview exists"}, "excluded": True},
        {"component": "eligibility", "points": elig_score, "max": config["eligibility"]["max_points"], "details": elig_details},
    ]
    available_max = sum(b["max"] for b in breakdown if not b.get("excluded"))
    raw = sum(b["points"] for b in breakdown if not b.get("excluded"))
    pct = round(raw / available_max * 100, 1) if available_max else 0.0
    total = round(pct, 2)  # normalised to a 0-100 scale

    have = canonical_set(student_profile.get("skills", []))
    req, pref = job.get("required_skills", []), job.get("preferred_skills", [])
    matched = [s for s in req + pref if canonical(s) in have]
    missing = [s for s in req if canonical(s) not in have]
    missing_pref = [s for s in pref if canonical(s) not in have]
    confidence = _compute_match_confidence(skill_score, coding_score, is_eligible, skill_details, config,
                                           coding_ok=coding_ok, stale=job.get("is_stale", False))

    reasons = [f"Matches {skill_details.get('matched_required', 0)}/{skill_details.get('total_required', 0)} required skills"
               + (f" (missing: {', '.join(missing)})" if missing else "")]
    if elig_details["fail_reasons"]:
        reasons.append("Not eligible: " + "; ".join(elig_details["fail_reasons"]))
    elif elig_details["required_gpa"]:
        reasons.append(f"Eligible: CGPA {elig_details['student_gpa']} ≥ {elig_details['required_gpa']} ({elig_details['gpa_source']})")
    reasons.append(f"Projects using listed skills: {project_details.get('matching_projects', 0)}/{project_details.get('total_projects', 0)}")
    if not coding_ok:
        reasons.append("Coding activity excluded (no consented coding data)")
    if job.get("is_stale"):
        reasons.append("Listing has not been re-verified recently — confirm it is still open")

    return {
        "job_id": job.get("job_id"),
        "company_name": job.get("company_name"),
        "role_title": job.get("role_title"),
        "role_family": job.get("role_family", "general"),
        "package_lpa": job.get("package_lpa"),
        "location": job.get("location"),
        "deadline": job.get("deadline"),
        "application_url": job.get("application_url"),
        "listing_source": job.get("source"),
        "listing_last_verified_at": job.get("last_verified_at"),
        "is_stale": job.get("is_stale", False),
        "target_role_match": _target_match(job, targets or []),
        "requirements": {"required": req, "preferred": pref, "min_cgpa": job.get("min_cgpa"),
                         "max_backlogs": job.get("max_backlogs"), "min_experience": job.get("min_experience")},
        "match_score": total,
        "max_score": 100.0,
        "match_percentage": pct,
        "excluded_components": excluded,
        "confidence": confidence,
        "is_eligible": is_eligible,
        "eligibility_verified": elig_details["verified"],
        "is_low_confidence": confidence < LOW_CONFIDENCE_THRESHOLD or job.get("is_stale", False) or not elig_details["verified"],
        "matched_skills": matched,
        "missing_skills": missing,
        "missing_preferred_skills": missing_pref,
        "reasoning": ". ".join(reasons) + ".",
        "application_status": "not_submitted",
        "breakdown": breakdown,
    }


def compute_readiness_score(skill_gap_report: Optional[Dict[str, Any]], coding_analytics: Optional[Dict[str, Any]],
                            student_profile: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Placement readiness against the student's *target roles* (not a single job):
    skill coverage from the gap report, coding performance, and project relevance
    to the union of verified requirements. Unassessed components are excluded.
    """
    coverage = (skill_gap_report or {}).get("overall_coverage", 0) or 0
    skill_pts = round(coverage / 100 * config["skill_coverage"]["max_points"], 2)
    coding_pts, coding_details = _compute_coding_performance_score(coding_analytics, config["coding_performance"]["max_points"])
    coding_ok = coding_details.get("available", False)
    req_skills = [g["skill"] for g in (skill_gap_report or {}).get("gaps", [])] + \
                 [s["skill"] for s in (skill_gap_report or {}).get("strengths", [])]
    proj_pts, proj_details = _compute_project_relevance_score(student_profile, {"required_skills": req_skills, "preferred_skills": []},
                                                              config["project_relevance"]["max_points"])
    breakdown = [
        {"component": "skill_coverage", "points": skill_pts, "max": config["skill_coverage"]["max_points"],
         "details": {"coverage": coverage, "source": (skill_gap_report or {}).get("citation")}},
        {"component": "coding_performance", "points": coding_pts, "max": config["coding_performance"]["max_points"],
         "details": coding_details, "excluded": not coding_ok},
        {"component": "project_relevance", "points": proj_pts, "max": config["project_relevance"]["max_points"], "details": proj_details},
        {"component": "interview_readiness", "points": 0.0, "max": config["interview_readiness"]["max_points"],
         "details": {"status": "not_assessed"}, "excluded": True},
    ]
    available = sum(b["max"] for b in breakdown if not b.get("excluded"))
    raw = sum(b["points"] for b in breakdown if not b.get("excluded"))
    pct = round(raw / available * 100, 1) if available else 0.0
    signals = []
    signals.append(f"Skill coverage {coverage}% of verified requirements")
    if coding_ok:
        signals.append(f"Coding performance {coding_pts}/{config['coding_performance']['max_points']} ({coding_details.get('basis')})")
    else:
        signals.append("Coding performance excluded — no consented coding data")
    signals.append(f"Projects aligned to target skills: {proj_details.get('matching_projects', 0)}/{proj_details.get('total_projects', 0)}")
    return {"total": pct, "max": 100.0, "percentage": pct, "breakdown": breakdown,
            "basis": "target_role_benchmarks", "signals": signals}


def job_matching_agent_node(state: PlacementState) -> Dict[str, Any]:
    """LangGraph node: Job Matching Agent."""
    profile = state.get("student_profile")
    if not profile:
        return {"errors": ["JobMatchingAgent: No student profile available."], "current_step": "job_matching_agent"}

    try:
        hub = get_hub(state)
        jobs = hub.active_jobs()
    except HubUnavailableError as exc:
        return {"errors": [f"JobMatchingAgent: {exc}"], "current_step": "job_matching_agent"}

    skill_gap_report = state.get("skill_gap_report")
    coding_analytics = state.get("coding_analytics")
    specialist = state.get("specialist_analysis") or {}
    config = scoring_config_from_weights(specialist.get("scoring_weights"))
    academic = (state.get("student_context") or {}).get("academic") or {}
    targets = resolve_targets(state.get("target_roles") or [])

    matches = [_score_single_job(profile, coding_analytics, job, config, academic, targets) for job in jobs]
    matches.sort(key=lambda m: (m["target_role_match"] is None, not m["is_eligible"], -m["match_score"]))

    low_conf = [
        f"{m['company_name']} - {m['role_title']}: confidence={m['confidence']}"
        + (" (stale listing)" if m["is_stale"] else "") + ("" if m["eligibility_verified"] else " (eligibility unverified)")
        for m in matches if m["is_low_confidence"]
    ]

    readiness = compute_readiness_score(skill_gap_report, coding_analytics, profile, config)
    target_matches = [m for m in matches if m["target_role_match"]]
    narrative = (f"Evaluated {len(matches)} open listing(s) from the placement database; "
                 f"{len(target_matches)} match your target roles and "
                 f"{sum(1 for m in matches if m['is_eligible'])} are eligible.")
    if not jobs:
        narrative = "No open job listings are in the placement database yet; matches will appear once the Placement Cell lists drives."

    llm = get_chat_model(temperature=0.2)
    narration_method = "deterministic"
    if llm is not None and matches:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            msg = llm.invoke([
                SystemMessage(content="In two sentences, give career advice from these pre-scored matches. "
                                      "Do not change scores, do not overstate fit, mention confidence."),
                HumanMessage(content=str([{k: m[k] for k in ("company_name", "role_title", "match_percentage", "confidence",
                                                               "is_eligible", "missing_skills")} for m in matches[:5]])),
            ])
            text = getattr(msg, "content", "")
            if isinstance(text, str) and text.strip():
                narrative += " [AI-generated advice] " + text.strip()[:500]
                narration_method = "llm"
        except Exception as exc:
            logger.warning(f"[JobMatchingAgent] narration unavailable: {exc}")

    matching_result = {
        "status": "ok" if matches else "no_active_jobs",
        "readiness_score": readiness,
        "matches": matches,
        "total_jobs_evaluated": len(matches),
        "eligible_count": sum(1 for m in matches if m["is_eligible"]),
        "target_role_match_count": len(target_matches),
        "low_confidence_flags": low_conf,
        "jobs_source": {"source": "companies_db", "listings": len(jobs)},
        "overall_narrative": narrative,
        "narration_method": narration_method,
        "application_policy": APPLICATION_POLICY,
        "applications_submitted": [],
        "scoring_config_used": {k: v["weight"] for k, v in config.items()},
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    evidence = [EvidenceRecord(
        entity_type="company_match", evidence_type="deterministic_scoring",
        source=f"jobs_db: {m['company_name']} — {m['role_title']} ({m['listing_source']})",
        content=(f"Score {m['match_score']}/100, confidence {m['confidence']}, eligible {m['is_eligible']}; "
                 f"required matched {m['breakdown'][0]['details'].get('matched_required')}/{m['breakdown'][0]['details'].get('total_required')}."),
        scope_tags=["matching", m.get("role_family", "general")],
    ).model_dump() for m in matches]
    evidence.append(EvidenceRecord(
        entity_type="readiness_score", evidence_type="deterministic_scoring", source="skill_gap_report + coding_analytics",
        content=f"Readiness {readiness['percentage']}% — " + "; ".join(readiness["signals"]),
        scope_tags=["readiness"],
    ).model_dump())

    audit = AuditEvent(action="job_matching_completed", agent="JobMatchingAgent",
                       timestamp=datetime.now(timezone.utc).isoformat(),
                       details={"jobs_evaluated": len(matches), "eligible": matching_result["eligible_count"],
                                "low_confidence": len(low_conf), "readiness": readiness["percentage"]})

    return {"matching_result": matching_result, "evidence_records": evidence, "audit_events": [audit],
            "current_step": "job_matching_agent"}
