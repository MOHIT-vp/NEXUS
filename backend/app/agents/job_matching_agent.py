"""
Job Matching Agent (A4) — Deterministic scoring engine + LLM match reasoning.

Architecture Contract:
- Input: student_profile, skill_gap_report, coding_analytics, available_roles, scoring_config
- Output: readiness_score (with component breakdown), ranked matches with confidence + reasoning
- Scoring: 100% DETERMINISTIC application code — NOT LLM
- LLM Usage: Match reasoning and explanation ONLY
- Constraints: Never overstate certainty, flag low-confidence (<0.6), provide evidence for each match

Readiness Score Formula:
    Total = Σ(component_score × component_weight)
    Components:
    - skill_coverage     (weight: 0.40, max: 40)
    - coding_performance (weight: 0.25, max: 25)
    - project_relevance  (weight: 0.15, max: 15)
    - interview_readiness(weight: 0.15, max: 15)  — placeholder until Interview Agent runs
    - eligibility        (weight: 0.05, max: 5)    — binary PASS/FAIL
"""
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from decimal import Decimal
import logging

from pydantic import BaseModel, Field

from app.config import settings
from app.agents.state import PlacementState, AuditEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class MatchReasoning(BaseModel):
    """LLM-generated reasoning for a single job match."""
    job_title: str
    company_name: str
    reasoning: str = Field(description="Specific, evidence-based reasoning for this match score")
    fit_highlights: List[str] = Field(description="Top 3 reasons this role is a good fit")
    concern_areas: List[str] = Field(description="Areas where the student may struggle in this role")


class MatchReasoningBatch(BaseModel):
    """LLM-generated reasonings for all matches."""
    overall_narrative: str = Field(description="1-2 sentence summary of the student's job market position")
    match_reasonings: List[MatchReasoning]
    career_advice: str = Field(description="Brief, actionable career advice based on the matching results")


# ---------------------------------------------------------------------------
# Default scoring configuration
# ---------------------------------------------------------------------------

DEFAULT_SCORING_CONFIG = {
    "skill_coverage": {"weight": 0.40, "max_points": 40},
    "coding_performance": {"weight": 0.25, "max_points": 25},
    "project_relevance": {"weight": 0.15, "max_points": 15},
    "interview_readiness": {"weight": 0.15, "max_points": 15},
    "eligibility": {"weight": 0.05, "max_points": 5},
}

LOW_CONFIDENCE_THRESHOLD = 0.6


# ---------------------------------------------------------------------------
# Mock job data (Lab 7)
# ---------------------------------------------------------------------------

def _get_mock_available_jobs() -> List[Dict[str, Any]]:
    """
    Returns available job listings from company_service (including newly listed drives).
    Falls back to baseline if company_service is not initialized.
    """
    try:
        from app.services.company_service import company_service
        drives = company_service.get_all_jobs_for_matching()
        if drives:
            return drives
    except Exception:
        pass

    return [
        {
            "job_id": "job-001",
            "company_name": "TechCorp Solutions",
            "role_title": "Software Engineer",
            "role_family": "software_engineering",
            "min_cgpa": 7.0,
            "min_experience": 0,
            "package_lpa": 12.0,
            "required_skills": ["Python", "JavaScript", "React.js", "SQL", "Git"],
            "preferred_skills": ["Docker", "AWS", "System Design"],
            "description": "Full-stack development role focusing on web applications.",
        },
        {
            "job_id": "job-002",
            "company_name": "DataDriven Inc.",
            "role_title": "Data Engineer",
            "role_family": "data_engineering",
            "min_cgpa": 7.5,
            "min_experience": 0,
            "package_lpa": 15.0,
            "required_skills": ["Python", "SQL", "Data Structures", "Algorithms"],
            "preferred_skills": ["Machine Learning", "Apache Spark", "AWS"],
            "description": "Building data pipelines and analytics infrastructure.",
        },
        {
            "job_id": "job-003",
            "company_name": "InnovateTech",
            "role_title": "Backend Developer",
            "role_family": "software_engineering",
            "min_cgpa": 6.5,
            "min_experience": 0,
            "package_lpa": 10.0,
            "required_skills": ["Python", "Node.js", "SQL", "Git"],
            "preferred_skills": ["Docker", "Kubernetes", "Redis"],
            "description": "API development and microservices architecture.",
        },
        {
            "job_id": "job-004",
            "company_name": "CloudFirst Systems",
            "role_title": "DevOps Engineer",
            "role_family": "devops",
            "min_cgpa": 7.0,
            "min_experience": 0,
            "package_lpa": 14.0,
            "required_skills": ["Docker", "Kubernetes", "AWS", "Linux", "Git"],
            "preferred_skills": ["Terraform", "Python", "CI/CD"],
            "description": "Infrastructure automation and deployment pipeline engineering.",
        },
        {
            "job_id": "job-005",
            "company_name": "FinSecure Analytics",
            "role_title": "Full Stack Developer",
            "role_family": "software_engineering",
            "min_cgpa": 7.0,
            "min_experience": 0,
            "package_lpa": 11.0,
            "required_skills": ["React.js", "Node.js", "JavaScript", "SQL"],
            "preferred_skills": ["TypeScript", "PostgreSQL", "Redis"],
            "description": "Building secure fintech web applications.",
        },
    ]


# ---------------------------------------------------------------------------
# Deterministic scoring functions
# ---------------------------------------------------------------------------

def _compute_skill_coverage_score(
    student_skills: List[Dict[str, Any]],
    required_skills: List[str],
    preferred_skills: List[str],
    max_points: float,
) -> Tuple[float, Dict[str, Any]]:
    """
    Deterministic skill coverage scoring.
    Required skills: full weight
    Preferred skills: 50% weight bonus (on top of required)
    """
    if not required_skills:
        return max_points, {"matched_required": 0, "total_required": 0}

    student_skill_names = {s.get("name", "").lower().strip() for s in student_skills}

    # Required skill matching
    required_matches = sum(1 for s in required_skills if s.lower() in student_skill_names)
    required_ratio = required_matches / len(required_skills)

    # Preferred skill bonus (up to 20% extra)
    preferred_matches = sum(1 for s in preferred_skills if s.lower() in student_skill_names) if preferred_skills else 0
    preferred_ratio = preferred_matches / len(preferred_skills) if preferred_skills else 0

    # Base score from required + bonus from preferred
    base_score = required_ratio * max_points * 0.85  # 85% of max from required
    bonus_score = preferred_ratio * max_points * 0.15  # 15% of max from preferred

    score = round(min(base_score + bonus_score, max_points), 2)

    details = {
        "matched_required": required_matches,
        "total_required": len(required_skills),
        "matched_preferred": preferred_matches,
        "total_preferred": len(preferred_skills),
        "required_ratio": round(required_ratio, 2),
    }

    return score, details


def _compute_coding_performance_score(
    coding_analytics: Optional[Dict[str, Any]],
    max_points: float,
) -> Tuple[float, Dict[str, Any]]:
    """
    Deterministic coding performance scoring.
    Uses the pre-computed coding percentile from the Coding Analytics Agent.
    """
    if not coding_analytics:
        return 0.0, {"reason": "No coding analytics available"}

    summary = coding_analytics.get("summary", {})
    percentile = summary.get("coding_percentile", 0)
    difficulty_score = summary.get("difficulty_score", 0)
    trend = summary.get("activity_trend", "stable")

    # Base: percentile maps directly to points (percentile/100 * max)
    base = (percentile / 100) * max_points * 0.7

    # Difficulty bonus: rewarding harder problems (up to 20% of max)
    difficulty_bonus = (difficulty_score / 100) * max_points * 0.2

    # Trend bonus: improving = +10%, stable = 0, declining = -5%
    trend_multipliers = {"improving": 0.10, "stable": 0.0, "declining": -0.05}
    trend_bonus = max_points * trend_multipliers.get(trend, 0)

    score = round(min(max(base + difficulty_bonus + trend_bonus, 0), max_points), 2)

    return score, {
        "percentile": percentile,
        "difficulty_score": difficulty_score,
        "trend": trend,
        "base_points": round(base, 2),
    }


def _compute_project_relevance_score(
    student_profile: Dict[str, Any],
    job: Dict[str, Any],
    max_points: float,
) -> Tuple[float, Dict[str, Any]]:
    """
    Deterministic project relevance scoring.
    Matches student project technologies against job requirements.
    """
    projects = student_profile.get("projects", [])
    if not projects:
        return 0.0, {"reason": "No projects found"}

    required = {s.lower() for s in job.get("required_skills", [])}
    preferred = {s.lower() for s in job.get("preferred_skills", [])}
    all_relevant = required | preferred

    matching_projects = 0
    total_tech_matches = 0

    for project in projects:
        techs = {t.lower() for t in project.get("technologies", [])}
        overlap = techs & all_relevant
        if overlap:
            matching_projects += 1
            total_tech_matches += len(overlap)

    if not projects:
        ratio = 0
    else:
        ratio = matching_projects / len(projects)

    # Score: combination of project match ratio and tech depth
    tech_depth = min(total_tech_matches / max(len(all_relevant), 1), 1.0)
    score = round(((ratio * 0.6) + (tech_depth * 0.4)) * max_points, 2)

    return score, {
        "matching_projects": matching_projects,
        "total_projects": len(projects),
        "tech_overlap_count": total_tech_matches,
    }


def _check_eligibility(
    student_profile: Dict[str, Any],
    job: Dict[str, Any],
    max_points: float,
) -> Tuple[float, bool, Dict[str, Any]]:
    """
    Deterministic eligibility check. Binary PASS/FAIL.
    Checks CGPA minimum and experience requirements.
    """
    # Extract student GPA from education data
    education = student_profile.get("education", {})
    student_gpa = education.get("gpa") if education else None

    min_cgpa = job.get("min_cgpa", 0)
    min_experience = job.get("min_experience", 0)

    reasons = []
    is_eligible = True

    # GPA check (only if both are available)
    if min_cgpa and student_gpa is not None:
        if float(student_gpa) < float(min_cgpa):
            is_eligible = False
            reasons.append(f"CGPA {student_gpa} below minimum {min_cgpa}")

    # Experience check
    years = student_profile.get("years_experience", 0)
    if min_experience and years < min_experience:
        is_eligible = False
        reasons.append(f"Experience {years}y below minimum {min_experience}y")

    score = max_points if is_eligible else 0.0

    return score, is_eligible, {
        "is_eligible": is_eligible,
        "student_gpa": student_gpa,
        "required_gpa": min_cgpa,
        "fail_reasons": reasons,
    }


def _compute_match_confidence(
    skill_score: float,
    coding_score: float,
    eligibility: bool,
    skill_details: Dict,
    config: Dict,
) -> float:
    """
    Compute confidence level for a match (0.0 - 1.0).
    Low confidence when:
    - Few data points available
    - Required skill coverage < 50%
    - Not eligible
    """
    if not eligibility:
        return 0.1  # Very low confidence for ineligible

    factors = []

    # Required skill coverage
    req_ratio = skill_details.get("required_ratio", 0)
    factors.append(req_ratio)

    # Coding data availability
    coding_available = 1.0 if coding_score > 0 else 0.3
    factors.append(coding_available)

    # Overall score proportion
    total_max = sum(c["max_points"] for c in config.values())
    total_score = skill_score + coding_score
    score_ratio = min(total_score / (total_max * 0.65), 1.0)  # Relative to 65% threshold
    factors.append(score_ratio)

    confidence = sum(factors) / len(factors)
    return round(min(max(confidence, 0.0), 1.0), 2)


def _score_single_job(
    student_profile: Dict[str, Any],
    coding_analytics: Optional[Dict[str, Any]],
    job: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Score a single job match. Returns the complete score breakdown."""

    # 1. Skill Coverage
    skill_score, skill_details = _compute_skill_coverage_score(
        student_profile.get("skills", []),
        job.get("required_skills", []),
        job.get("preferred_skills", []),
        config["skill_coverage"]["max_points"],
    )

    # 2. Coding Performance
    coding_score, coding_details = _compute_coding_performance_score(
        coding_analytics,
        config["coding_performance"]["max_points"],
    )

    # 3. Project Relevance
    project_score, project_details = _compute_project_relevance_score(
        student_profile,
        job,
        config["project_relevance"]["max_points"],
    )

    # 4. Interview Readiness (placeholder — will be updated by Interview Agent)
    interview_score = config["interview_readiness"]["max_points"] * 0.5  # Neutral default
    interview_details = {"status": "pending_interview_agent"}

    # 5. Eligibility
    eligibility_score, is_eligible, eligibility_details = _check_eligibility(
        student_profile,
        job,
        config["eligibility"]["max_points"],
    )

    # Total
    total_score = round(
        skill_score + coding_score + project_score + interview_score + eligibility_score, 2
    )
    max_total = sum(c["max_points"] for c in config.values())

    # Extract matched and missing skill lists using canonicalization
    try:
        from app.services.company_service import canonicalize_skill
    except Exception:
        canonicalize_skill = lambda s: s.strip().lower()

    student_skill_names = {s.get("name", "").lower().strip() for s in student_profile.get("skills", [])}
    student_canonical = {canonicalize_skill(s.get("name", "")) for s in student_profile.get("skills", [])}
    req_skills = job.get("required_skills", [])
    pref_skills = job.get("preferred_skills", [])
    matched_skills = [
        s for s in req_skills + pref_skills
        if s.lower().strip() in student_skill_names or canonicalize_skill(s) in student_canonical
    ]
    missing_skills = [
        s for s in req_skills
        if s.lower().strip() not in student_skill_names and canonicalize_skill(s) not in student_canonical
    ]

    # Confidence
    confidence = _compute_match_confidence(
        skill_score, coding_score, is_eligible, skill_details, config
    )

    return {
        "job_id": job.get("job_id"),
        "company_name": job.get("company_name"),
        "role_title": job.get("role_title"),
        "role_family": job.get("role_family", "general"),
        "package_lpa": job.get("package_lpa"),
        "match_score": total_score,
        "max_score": max_total,
        "match_percentage": round((total_score / max_total) * 100, 1) if max_total > 0 else 0,
        "confidence": confidence,
        "is_eligible": is_eligible,
        "is_low_confidence": confidence < LOW_CONFIDENCE_THRESHOLD,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "breakdown": [
            {"component": "skill_coverage", "points": skill_score,
             "max": config["skill_coverage"]["max_points"], "details": skill_details},
            {"component": "coding_performance", "points": coding_score,
             "max": config["coding_performance"]["max_points"], "details": coding_details},
            {"component": "project_relevance", "points": project_score,
             "max": config["project_relevance"]["max_points"], "details": project_details},
            {"component": "interview_readiness", "points": interview_score,
             "max": config["interview_readiness"]["max_points"], "details": interview_details},
            {"component": "eligibility", "points": eligibility_score,
             "max": config["eligibility"]["max_points"], "details": eligibility_details},
        ],
    }


def _get_llm():
    """Get LLM for match reasoning only (lazy import)."""
    from langchain_core.messages import SystemMessage, HumanMessage  # noqa: F401
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        temperature=0.2,
        google_api_key=settings.LLM_API_KEY if settings.LLM_API_KEY else "dummy",
    )


# ---------------------------------------------------------------------------
# Main Agent Node
# ---------------------------------------------------------------------------

def job_matching_agent_node(state: PlacementState) -> Dict[str, Any]:
    """
    LangGraph Node: Job Matching Agent.

    1. Reads student_profile, skill_gap_report, coding_analytics from state
    2. Fetches available jobs (mock for Lab 7)
    3. Runs DETERMINISTIC scoring engine for each job
    4. Ranks jobs by match score
    5. Uses LLM ONLY for reasoning/explanation generation
    6. Flags low-confidence matches
    7. Returns matching_result to state
    """
    logger.info("[JobMatchingAgent] Starting job matching and scoring...")

    student_profile = state.get("student_profile")
    if not student_profile:
        return {
            "errors": ["JobMatchingAgent: No student profile available."],
            "current_step": "job_matching_agent",
        }

    skill_gap_report = state.get("skill_gap_report")
    coding_analytics = state.get("coding_analytics")

    # ---------- STEP 1: Get available jobs ----------
    available_jobs = _get_mock_available_jobs()
    scoring_config = DEFAULT_SCORING_CONFIG

    # ---------- STEP 2: Score every job deterministically ----------
    scored_matches = []
    for job in available_jobs:
        match = _score_single_job(student_profile, coding_analytics, job, scoring_config)
        scored_matches.append(match)

    # ---------- STEP 3: Rank by score descending ----------
    scored_matches.sort(key=lambda x: x["match_score"], reverse=True)

    # ---------- STEP 4: Compute readiness score (top match or average) ----------
    if scored_matches:
        top_match = scored_matches[0]
        readiness_score = {
            "total": top_match["match_score"],
            "max": top_match["max_score"],
            "percentage": top_match["match_percentage"],
            "breakdown": top_match["breakdown"],
        }
    else:
        readiness_score = {"total": 0, "max": 100, "percentage": 0, "breakdown": []}

    # ---------- STEP 5: Flag low-confidence matches ----------
    low_confidence_flags = []
    for m in scored_matches:
        if m["is_low_confidence"]:
            low_confidence_flags.append(
                f"{m['company_name']} - {m['role_title']}: confidence={m['confidence']} "
                f"(below threshold {LOW_CONFIDENCE_THRESHOLD})"
            )

    # ---------- STEP 6: LLM reasoning ----------
    try:
        llm = _get_llm().with_structured_output(MatchReasoningBatch)

        # Build a compact summary for the LLM (no raw data leaks)
        matches_summary = []
        for m in scored_matches[:5]:  # Only reason on top 5
            matches_summary.append({
                "job": f"{m['company_name']} - {m['role_title']}",
                "score": f"{m['match_percentage']}%",
                "confidence": m["confidence"],
                "eligible": m["is_eligible"],
                "skill_coverage": next(
                    (b["details"].get("required_ratio", 0) for b in m["breakdown"]
                     if b["component"] == "skill_coverage"), 0
                ),
            })

        coding_pct = coding_analytics.get("summary", {}).get("coding_percentile", "N/A") if coding_analytics else "N/A"
        student_skill_names = [s.get('name') for s in student_profile.get('skills', [])]
        project_count = len(student_profile.get('projects', []))
        skill_cov = skill_gap_report.get('overall_coverage', 'N/A') if skill_gap_report else 'N/A'

        reasoning_prompt = f"""
        You are the Job Matching Agent for a Placement Readiness system.

        CRITICAL RULES:
        1. Never overstate certainty — always include confidence levels
        2. Low-confidence matches (confidence < {LOW_CONFIDENCE_THRESHOLD}) MUST be flagged explicitly
        3. Provide specific, evidence-based reasoning for each match
        4. The scoring numbers come from the scoring engine — do NOT recalculate
        5. Be honest but constructive

        STUDENT PROFILE SUMMARY:
        - Skills: {student_skill_names}
        - Projects: {project_count} projects
        - Skill Coverage: {skill_cov}%
        - Coding Percentile: {coding_pct}%

        SCORED MATCHES (ranked by score — these are GROUND TRUTH):
        {matches_summary}

        LOW CONFIDENCE FLAGS:
        {low_confidence_flags if low_confidence_flags else 'None'}

        Generate specific reasoning for each match. Reference actual skill overlaps and gaps.
        """

        reasoning: MatchReasoningBatch = llm.invoke([
            SystemMessage(content=reasoning_prompt),
            HumanMessage(content="Generate match reasonings based on the scoring data above.")
        ])

        # Attach reasoning to matches
        reasoning_map = {
            f"{r.company_name} - {r.job_title}".lower(): r
            for r in reasoning.match_reasonings
        }

        for m in scored_matches:
            key = f"{m['company_name']} - {m['role_title']}".lower()
            if key in reasoning_map:
                r = reasoning_map[key]
                m["reasoning"] = r.reasoning
                m["fit_highlights"] = r.fit_highlights
                m["concern_areas"] = r.concern_areas
            else:
                m["reasoning"] = f"Match score: {m['match_percentage']}%"
                m["fit_highlights"] = []
                m["concern_areas"] = []

        overall_narrative = reasoning.overall_narrative
        career_advice = reasoning.career_advice

    except Exception as e:
        logger.warning(f"[JobMatchingAgent] LLM reasoning failed, using fallback: {e}")
        for m in scored_matches:
            m["reasoning"] = (
                f"Match score: {m['match_percentage']}% "
                f"(confidence: {m['confidence']}). "
                f"{'Eligible' if m['is_eligible'] else 'NOT eligible — does not meet minimum requirements'}."
            )
            m["fit_highlights"] = []
            m["concern_areas"] = []
        overall_narrative = f"Scored {len(scored_matches)} job matches."
        career_advice = "Focus on closing skill gaps to improve match scores."

    # ---------- STEP 7: Assemble final result ----------
    matching_result = {
        "readiness_score": readiness_score,
        "matches": scored_matches,
        "total_jobs_evaluated": len(scored_matches),
        "eligible_count": sum(1 for m in scored_matches if m["is_eligible"]),
        "low_confidence_flags": low_confidence_flags,
        "overall_narrative": overall_narrative,
        "career_advice": career_advice,
        "scoring_config_used": {k: v["weight"] for k, v in scoring_config.items()},
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    # ---------- STEP 8: Evidence records ----------
    from app.schemas.evidence import EvidenceRecord
    evidence_records = []
    for m in scored_matches:
        evidence_records.append(EvidenceRecord(
            entity_type="company_match",
            evidence_type="deterministic_scoring",
            source="job_matching_agent",
            content=f"Job: {m['company_name']} - {m['role_title']}, "
                       f"Score: {m['match_score']}/{m['max_score']}, "
                       f"Confidence: {m['confidence']}, "
                       f"Eligible: {m['is_eligible']}",
            scope_tags=["matching", "scoring", m.get("role_family", "general")],
        ).model_dump())

    audit = AuditEvent(
        action="job_matching_completed",
        agent="JobMatchingAgent",
        timestamp=datetime.now(timezone.utc).isoformat(),
        details={
            "jobs_evaluated": len(scored_matches),
            "eligible_count": sum(1 for m in scored_matches if m["is_eligible"]),
            "top_match": scored_matches[0]["match_percentage"] if scored_matches else 0,
            "low_confidence_count": len(low_confidence_flags),
        }
    )

    logger.info(
        f"[JobMatchingAgent] Complete — Evaluated: {len(scored_matches)} jobs, "
        f"Eligible: {sum(1 for m in scored_matches if m['is_eligible'])}, "
        f"Top Match: {scored_matches[0]['match_percentage'] if scored_matches else 0}%"
    )

    return {
        "matching_result": matching_result,
        "evidence_records": evidence_records,
        "audit_events": [audit],
        "current_step": "job_matching_agent",
    }
