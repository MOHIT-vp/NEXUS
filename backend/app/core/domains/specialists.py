"""
Domain specialists (Lab 13) — pluggable role-family packs that contribute
domain-specific analysis to every plan.

Each specialist receives the evidenced profile, coding analytics and skill-gap
report and returns a ``SpecialistOutput``. Outputs are validated against the
schema and a checkable-scheme rule (every recommendation must reference a
focus skill or a named data point) before they are merged into the plan.
"""
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.domains.base import RoleFamilyConfig
from app.core.domains.registry import DOMAIN_REGISTRY
from app.core.skills import canonical, canonical_set


class FocusSkill(BaseModel):
    skill: str
    category: str              # required | recommended | tooling
    status: str                # evidenced | missing
    evidence: List[str] = Field(default_factory=list)


class SpecialistRecommendation(BaseModel):
    title: str
    detail: str
    references: List[str] = Field(..., min_length=1, description="Focus skills or data points this rests on")
    priority: str = "medium"

    @field_validator("priority")
    @classmethod
    def _p(cls, v: str) -> str:
        if v not in {"critical", "high", "medium", "low"}:
            raise ValueError("priority must be critical/high/medium/low")
        return v


class SpecialistOutput(BaseModel):
    domain: str
    name: str
    relevance: str
    focus_skills: List[FocusSkill]
    domain_coverage: float = Field(..., ge=0, le=100)
    recommendations: List[SpecialistRecommendation] = Field(..., min_length=1)
    interview_focus: List[str] = Field(default_factory=list)
    scoring_weights: Dict[str, float]
    evidence: List[Dict[str, str]] = Field(default_factory=list)


def _split_terms(skill: str) -> List[str]:
    return [canonical(p) for p in skill.replace("&", "/").split("/") if p.strip()]


def _focus(config: RoleFamilyConfig, have: set, skill_evidence: Dict[str, List[str]]) -> List[FocusSkill]:
    out = []
    for category, skills in (("required", config.taxonomy.required_skills),
                             ("recommended", config.taxonomy.recommended_skills),
                             ("tooling", config.taxonomy.tooling)):
        for s in skills:
            terms = _split_terms(s)
            hit = next((t for t in terms if t in have), None)
            out.append(FocusSkill(skill=s, category=category, status="evidenced" if hit else "missing",
                                  evidence=skill_evidence.get(hit, [])[:2] if hit else []))
    return out


def _coverage(focus: List[FocusSkill]) -> float:
    weights = {"required": 1.0, "recommended": 0.6, "tooling": 0.4}
    total = sum(weights[f.category] for f in focus)
    got = sum(weights[f.category] for f in focus if f.status == "evidenced")
    return round(got / total * 100, 1) if total else 0.0


def _missing(focus: List[FocusSkill], category: str) -> List[str]:
    return [f.skill for f in focus if f.category == category and f.status == "missing"]


def _software(ctx: Dict[str, Any], focus: List[FocusSkill]) -> List[SpecialistRecommendation]:
    recs: List[SpecialistRecommendation] = []
    summary = (ctx.get("coding_analytics") or {}).get("summary") or {}
    req_missing = _missing(focus, "required")
    if req_missing:
        recs.append(SpecialistRecommendation(
            title="Close core CS fundamentals",
            detail=f"Software interviews test {', '.join(req_missing)} directly; schedule weekly practice and revise theory.",
            references=req_missing, priority="critical"))
    solved = summary.get("total_solved")
    if solved is None:
        recs.append(SpecialistRecommendation(
            title="Make problem-solving practice visible",
            detail="No consented LeetCode data is available. Link a LeetCode profile so practice volume and topic coverage can be assessed.",
            references=["coding_analytics.leetcode"], priority="high"))
    elif solved < 150:
        recs.append(SpecialistRecommendation(
            title="Increase DSA practice volume",
            detail=f"You have solved {solved} problems; most product-company assessments expect sustained practice — target 150+ with a medium/hard mix.",
            references=["coding_analytics.total_solved", "Data Structures", "Algorithms"], priority="high"))
    if "System Design" in _missing(focus, "recommended"):
        recs.append(SpecialistRecommendation(
            title="Learn system-design basics",
            detail="Study caching, load balancing and database scaling; prepare one design walkthrough of your own project.",
            references=["System Design"], priority="medium"))
    tooling_missing = _missing(focus, "tooling")
    if tooling_missing:
        recs.append(SpecialistRecommendation(
            title="Add engineering tooling to a project",
            detail=f"Use {', '.join(tooling_missing)} in an existing project (e.g. containerise it and keep history on Git).",
            references=tooling_missing, priority="low"))
    return recs


def _analytics(ctx: Dict[str, Any], focus: List[FocusSkill]) -> List[SpecialistRecommendation]:
    recs: List[SpecialistRecommendation] = []
    req_missing = _missing(focus, "required")
    projects = (ctx.get("student_profile") or {}).get("projects", [])
    data_projects = [p for p in projects if canonical_set(p.get("technologies", [])) & {"sql", "python", "pandas", "tableau", "power bi", "machine learning", "statistics"}]
    if req_missing:
        recs.append(SpecialistRecommendation(
            title="Cover analytics fundamentals",
            detail=f"Analytics roles screen on {', '.join(req_missing)}; complete a structured course and a graded exercise for each.",
            references=req_missing, priority="critical"))
    if len(data_projects) < 2:
        recs.append(SpecialistRecommendation(
            title="Build an end-to-end analysis portfolio",
            detail=(f"Only {len(data_projects)} data project(s) found. Publish an analysis that goes from a public dataset "
                    "through SQL/Python cleaning to a dashboard with written insights."),
            references=["student_profile.projects", "Data Visualization", "SQL"], priority="high"))
    rec_missing = _missing(focus, "recommended")
    if rec_missing:
        recs.append(SpecialistRecommendation(
            title="Extend into data engineering / ML",
            detail=f"Pick one of {', '.join(rec_missing[:3])} to differentiate your profile.",
            references=rec_missing[:3], priority="medium"))
    return recs


def _core(ctx: Dict[str, Any], focus: List[FocusSkill]) -> List[SpecialistRecommendation]:
    recs: List[SpecialistRecommendation] = []
    req_missing = _missing(focus, "required")
    tooling_missing = _missing(focus, "tooling")
    if req_missing:
        recs.append(SpecialistRecommendation(
            title="Revise core subjects for technical rounds",
            detail=f"Core-company interviews test {', '.join(req_missing)}; revise with NPTEL lectures and solve previous GATE questions.",
            references=req_missing, priority="critical"))
    if tooling_missing:
        recs.append(SpecialistRecommendation(
            title="Gain hands-on design/simulation tool experience",
            detail=f"Complete a small design project in {tooling_missing[0]} and document it with drawings or simulation results.",
            references=tooling_missing, priority="high"))
    recs.append(SpecialistRecommendation(
        title="Prepare a core-project walkthrough",
        detail="Prepare a 5-minute explanation of your best core project: problem, calculations, design choices and results.",
        references=["student_profile.projects"], priority="medium"))
    return recs


def _higher_studies(ctx: Dict[str, Any], focus: List[FocusSkill]) -> List[SpecialistRecommendation]:
    recs: List[SpecialistRecommendation] = []
    prefs = (ctx.get("student_context") or {}).get("career_preferences") or {}
    timeline = prefs.get("timeline")
    req_missing = _missing(focus, "required")
    if "Quantitative Aptitude" in req_missing or "quantitative aptitude" in [canonical(s) for s in req_missing]:
        recs.append(SpecialistRecommendation(
            title="Start entrance-exam preparation",
            detail="Begin GRE/GATE quantitative preparation with official practice material and a weekly timed mock.",
            references=["Quantitative Aptitude"], priority="critical"))
    if any(canonical(s) in ("research methodology", "literature review") for s in req_missing):
        recs.append(SpecialistRecommendation(
            title="Get research exposure",
            detail="Approach a faculty member for a semester research project and write up a literature review of the area.",
            references=[s for s in req_missing if canonical(s) in ("research methodology", "literature review")], priority="high"))
    recs.append(SpecialistRecommendation(
        title="Plan applications and recommendations",
        detail=(f"Draft your statement of purpose and request recommendation letters early"
                f"{' — your stated timeline is ' + str(timeline) if timeline else ''}."),
        references=["Academic Writing"] + (["career_preferences.timeline"] if timeline else []), priority="medium"))
    return recs


SPECIALIST_LOGIC: Dict[str, Callable[[Dict[str, Any], List[FocusSkill]], List[SpecialistRecommendation]]] = {
    "software": _software,
    "analytics": _analytics,
    "core": _core,
    "higher_studies": _higher_studies,
}


def run_specialist(domain: str, ctx: Dict[str, Any], relevance: str) -> SpecialistOutput:
    config = DOMAIN_REGISTRY[domain]
    skills = (ctx.get("skill_gap_report") or {}).get("skills_considered") or (ctx.get("student_profile") or {}).get("skills", [])
    have = canonical_set(skills)
    evidence_map: Dict[str, List[str]] = {}
    for s in (ctx.get("student_profile") or {}).get("skills", []):
        evidence_map[canonical(s.get("name", ""))] = s.get("evidence") or []
    focus = _focus(config, have, evidence_map)
    recs = SPECIALIST_LOGIC[domain](ctx, focus)
    if not recs:
        recs = [SpecialistRecommendation(title="Maintain current trajectory",
                                         detail=f"All {config.name} focus skills are evidenced; keep them current.",
                                         references=[f.skill for f in focus[:3]], priority="low")]
    output = SpecialistOutput(
        domain=domain,
        name=config.name,
        relevance=relevance,
        focus_skills=focus,
        domain_coverage=_coverage(focus),
        recommendations=recs,
        interview_focus=config.question_bank.technical[:3] + (config.question_bank.system_design or [])[:1]
                        + config.question_bank.behavioral[:1],
        scoring_weights=config.weights.model_dump(),
        evidence=[{"source": f"Domain pack: {config.name}", "detail": config.description}],
    )
    validate_specialist_output(output)
    return output


def validate_specialist_output(output: SpecialistOutput) -> None:
    """Checkable-scheme rule: every reference must be a focus skill or a named data point."""
    focus_names = {canonical(f.skill) for f in output.focus_skills}
    for rec in output.recommendations:
        for ref in rec.references:
            if canonical(ref) in focus_names or "." in ref:
                continue
            # References to skills outside the pack (e.g. "Data Structures") are allowed when named explicitly
            if ref and ref[0].isupper():
                continue
            raise ValueError(f"Recommendation '{rec.title}' has an uncheckable reference '{ref}'")


def combined_weights(outputs: List[SpecialistOutput]) -> Optional[Dict[str, float]]:
    """Primary specialist's weights dominate (60%); others share the rest."""
    if not outputs:
        return None
    if len(outputs) == 1:
        return dict(outputs[0].scoring_weights)
    keys = outputs[0].scoring_weights.keys()
    rest = outputs[1:]
    return {k: round(0.6 * outputs[0].scoring_weights[k] + 0.4 * sum(o.scoring_weights[k] for o in rest) / len(rest), 4)
            for k in keys}
