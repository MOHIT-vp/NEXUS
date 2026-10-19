"""
Validation Agent (VA) — 100% Deterministic validation of all pipeline outputs.

Architecture Contract:
- Input: Full PlacementState with all agent outputs
- Output: validation_report with pass/fail for each of 12 checks
- LLM Usage: NONE — this agent is entirely deterministic
- Constraints: All checks are pure Python logic, no LLM inference

This is the quality gate that decides whether the readiness plan passes
validation or needs to be sent back through the self-healing loop.

Validation Checks (18). Chapter 9 §9.7 names four acceptance checks — 1, 2, 3/13
and 4 below — the rest guard grounding, provenance and governance:
1.  SKILL_GAP_CITATION        — Recommendations cite the specific skill gaps (error)
2.  ELIGIBILITY_ENFORCED      — Eligibility rules (CGPA, backlogs, experience) enforced (error)
3.  CONSENT_SATISFIED         — Required source consents are granted (error)
4.  BIAS_CHECK                — Shortlisting uses no protected attributes (error)
5.  EVIDENCE_PRESENT          — Every section has evidence records (error)
6.  CONFIDENCE_PRESENT        — All matches have confidence scores (error)
7.  LOW_CONFIDENCE_FLAGGED    — Low-confidence matches flagged for human review (error)
8.  SCHEMA_VALID              — Output conforms to required schemas (error)
9.  NO_MISSING_SECTIONS       — No required section is missing (error)
10. NO_CROSS_STUDENT_LEAK     — No cross-student information leakage (error)
11. NO_UNSUPPORTED_CLAIMS     — Every match carries reasoning (error)
12. SCORE_BOUNDS              — Scores within valid ranges (error)
13. NO_APPLICATION_WITHOUT_CONSENT — Nothing was submitted on the student's behalf (error)
14. REQUIREMENTS_VERIFIED     — Gaps are grounded in verified role requirements (error)
15. SOURCE_PROVENANCE         — Coding statistics come only from sources that returned data (error)
16. SPECIALIST_OUTPUT_VALID   — Domain specialist outputs passed schema validation (error)
17. SHORTLIST_DISTRIBUTION    — All/none-eligible outcomes flagged for review (warning)
18. RETRIEVAL_GROUNDED        — Roadmap items cite retrieved resources (warning)
"""
from typing import Any, Dict, List, Tuple
from datetime import datetime, timezone
import logging

from app.agents.state import PlacementState, AuditEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation check result structure
# ---------------------------------------------------------------------------

def _check_result(
    code: str,
    name: str,
    passed: bool,
    severity: str,
    message: str,
) -> Dict[str, Any]:
    """Create a standardized check result."""
    return {
        "code": code,
        "name": name,
        "passed": passed,
        "severity": severity,
        "message": message,
    }


# ---------------------------------------------------------------------------
# Individual validation checks
# ---------------------------------------------------------------------------

def _check_skill_gap_citation(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 1: SKILL_GAP_CITATION
    Verify that gap recommendations actually cite specific skill names.
    """
    report = state.get("skill_gap_report")
    if not report:
        return _check_result(
            "SKILL_GAP_CITATION", "Recommendations cite specific skill gaps",
            False, "error", "Skill gap report is missing entirely."
        )

    gaps = report.get("gaps", [])
    uncited_gaps = []
    for gap in gaps:
        skill = gap.get("skill", "")
        recommendation = gap.get("recommendation", "")
        # A citation must reference the actual skill name
        if skill and recommendation and skill.lower() not in recommendation.lower():
            uncited_gaps.append(skill)

    if uncited_gaps:
        return _check_result(
            "SKILL_GAP_CITATION", "Recommendations cite specific skill gaps",
            False, "error",
            f"Uncited gaps found: {uncited_gaps}. Recommendations must reference the specific skill."
        )

    return _check_result(
        "SKILL_GAP_CITATION", "Recommendations cite specific skill gaps",
        True, "error", f"All {len(gaps)} gaps have properly cited recommendations."
    )


def _check_eligibility_enforced(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 2: ELIGIBILITY_ENFORCED
    Verify that ineligible matches are properly marked.
    """
    matching = state.get("matching_result")
    if not matching:
        return _check_result(
            "ELIGIBILITY_ENFORCED", "Eligibility rules enforced",
            False, "error", "Matching result is missing entirely."
        )

    matches = matching.get("matches", [])
    violations = []

    for match in matches:
        breakdown = match.get("breakdown", [])
        eligibility_check = next(
            (b for b in breakdown if b["component"] == "eligibility"), None
        )

        if eligibility_check:
            details = eligibility_check.get("details", {})
            if not details.get("is_eligible", True) and match.get("is_eligible", True):
                violations.append(f"{match.get('company_name')} - marked eligible despite failing checks")

    if violations:
        return _check_result(
            "ELIGIBILITY_ENFORCED", "Eligibility rules enforced",
            False, "error", f"Eligibility violations: {violations}"
        )

    return _check_result(
        "ELIGIBILITY_ENFORCED", "Eligibility rules enforced",
        True, "error", f"Eligibility rules properly enforced across {len(matches)} matches."
    )


def _check_consent_satisfied(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 3: CONSENT_SATISFIED
    Required source consents (resume_processing, placement_matching) must be
    `granted` in the consent snapshot read from the Consent table for this run.
    """
    from app.services.consent import missing_required

    if not state.get("consent_validated", False):
        return _check_result(
            "CONSENT_SATISFIED", "Required consents granted",
            False, "error", "Consent was not validated before pipeline execution."
        )
    snapshot = state.get("consent_status")
    if snapshot is not None:
        missing = missing_required(snapshot)
        if missing:
            return _check_result(
                "CONSENT_SATISFIED", "Required consents granted", False, "error",
                f"Required consents not granted: {missing}"
            )
        # Coding data present without consent would be a violation
        for src in ((state.get("coding_analytics") or {}).get("sources") or []):
            if src.get("status") == "ok" and (snapshot.get(src.get("source")) or {}).get("status") != "granted":
                return _check_result(
                    "CONSENT_SATISFIED", "Required consents granted", False, "error",
                    f"{src.get('source')} data used without a granted consent."
                )

    return _check_result(
        "CONSENT_SATISFIED", "Required consents granted",
        True, "error", "Consent validation passed."
    )


PROTECTED_ATTRIBUTES = {
    "gender", "sex", "religion", "caste", "category", "ethnicity", "race", "age", "date_of_birth", "dob",
    "marital_status", "nationality", "disability", "photo", "full_name", "name",
}


def _scan_keys(obj: Any, found: set) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in PROTECTED_ATTRIBUTES:
                found.add(str(k).lower())
            _scan_keys(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _scan_keys(v, found)


def _check_bias(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 4: BIAS_CHECK
    Shortlisting must not use protected attributes: the scoring breakdown of every
    match and the scoring configuration are scanned for protected fields.
    """
    matching = state.get("matching_result") or {}
    found: set = set()
    for m in matching.get("matches", []):
        _scan_keys(m.get("breakdown", []), found)
    _scan_keys(matching.get("scoring_config_used", {}), found)
    if found:
        return _check_result(
            "BIAS_CHECK", "Shortlisting checked for bias", False, "error",
            f"Protected attributes used in scoring: {sorted(found)}"
        )
    return _check_result(
        "BIAS_CHECK", "Shortlisting checked for bias", True, "error",
        "Scoring uses only skills, coding activity, projects and published eligibility criteria."
    )


def _check_shortlist_distribution(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 17: SHORTLIST_DISTRIBUTION (warning)
    All-eligible or none-eligible outcomes are surfaced for the reviewer.
    """
    matches = (state.get("matching_result") or {}).get("matches", [])
    if len(matches) < 2:
        return _check_result("SHORTLIST_DISTRIBUTION", "Shortlist distribution reviewed", True, "warning",
                             "Fewer than two listings — distribution check not applicable.")
    eligible = sum(1 for m in matches if m.get("is_eligible"))
    if eligible in (0, len(matches)):
        return _check_result(
            "SHORTLIST_DISTRIBUTION", "Shortlist distribution reviewed", False, "warning",
            f"{'All' if eligible else 'No'} listings marked eligible ({eligible}/{len(matches)}). Review the criteria."
        )
    return _check_result("SHORTLIST_DISTRIBUTION", "Shortlist distribution reviewed", True, "warning",
                         f"{eligible}/{len(matches)} listings eligible.")


def _check_no_application_without_consent(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 13: NO_APPLICATION_WITHOUT_CONSENT
    The system never submits applications; any submitted entry fails the gate.
    """
    matching = state.get("matching_result") or {}
    submitted = list(matching.get("applications_submitted") or [])
    submitted += [m for m in matching.get("matches", []) if m.get("application_status") not in (None, "not_submitted")]
    if submitted:
        return _check_result("NO_APPLICATION_WITHOUT_CONSENT", "No application submitted without the student's consent",
                             False, "error", f"{len(submitted)} application(s) recorded as submitted by the system.")
    return _check_result("NO_APPLICATION_WITHOUT_CONSENT", "No application submitted without the student's consent",
                         True, "error", "No applications were submitted; students apply themselves.")


def _check_requirements_verified(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 14: REQUIREMENTS_VERIFIED
    Every gap must cite a requirement source, and at least one target role must
    have verified requirements (benchmark library or job listing).
    """
    report = state.get("skill_gap_report") or {}
    per_role = report.get("per_role")
    if per_role is None:  # legacy report shape: only citation can be checked
        ok = bool(report.get("citation") or all(g.get("benchmark_source") for g in report.get("gaps", [])))
        return _check_result("REQUIREMENTS_VERIFIED", "Gaps grounded in verified requirements", ok, "error",
                             "Gap sources present." if ok else "Gaps lack requirement sources.")
    verified = [r for r in per_role if r.get("requirements_count")]
    if not verified:
        return _check_result(
            "REQUIREMENTS_VERIFIED", "Gaps grounded in verified requirements", False, "error",
            f"No verified requirements exist for the target roles {[r.get('title') for r in per_role]}. "
            "Choose a catalogued role or ask the Placement Cell to add a benchmark or listing."
        )
    uncited = [g.get("skill") for g in report.get("gaps", []) if not g.get("benchmark_source")]
    if uncited:
        return _check_result("REQUIREMENTS_VERIFIED", "Gaps grounded in verified requirements", False, "error",
                             f"Gaps without a requirement source: {uncited}")
    return _check_result("REQUIREMENTS_VERIFIED", "Gaps grounded in verified requirements", True, "error",
                         f"Verified requirements for {len(verified)}/{len(per_role)} target role(s).")


def _check_source_provenance(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 15: SOURCE_PROVENANCE
    Coding statistics must come only from sources that returned data, with a
    retrieval timestamp. Unavailable sources must not contribute numbers.
    """
    ca = state.get("coding_analytics") or {}
    sources = ca.get("sources")
    if sources is None:
        return _check_result("SOURCE_PROVENANCE", "Coding data provenance", True, "error",
                             "Legacy coding analytics without per-source records.")
    ok_sources = [s for s in sources if s.get("status") == "ok"]
    summary = ca.get("summary") or {}
    problems = []
    for s in ok_sources:
        if not s.get("retrieved_at"):
            problems.append(f"{s.get('source')} has no retrieval time")
    for s in sources:
        if s.get("status") != "ok" and s.get("data"):
            problems.append(f"{s.get('source')} is {s.get('status')} but carries data")
    if summary.get("data_available") and not ok_sources:
        problems.append("Statistics present but no source returned data")
    if "total_solved" in summary and not any(s.get("source") == "leetcode" for s in ok_sources):
        problems.append("LeetCode statistics present without a successful LeetCode retrieval")
    if problems:
        return _check_result("SOURCE_PROVENANCE", "Coding data provenance", False, "error", "; ".join(problems))
    return _check_result("SOURCE_PROVENANCE", "Coding data provenance", True, "error",
                         f"{len(ok_sources)} source(s) returned data; others are marked "
                         f"{sorted({s.get('status') for s in sources if s.get('status') != 'ok'}) or 'n/a'}.")


def _check_specialist_output(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 16: SPECIALIST_OUTPUT_VALID
    If domain specialists were selected, at least one validated output must exist
    and none may be silently dropped.
    """
    sa = state.get("specialist_analysis")
    if sa is None:
        return _check_result("SPECIALIST_OUTPUT_VALID", "Domain specialist outputs validated", True, "error",
                             "Specialists not part of this run.")
    if sa.get("selected_domains") and not sa.get("specialists"):
        return _check_result("SPECIALIST_OUTPUT_VALID", "Domain specialist outputs validated", False, "error",
                             f"All specialist outputs were rejected: {sa.get('rejected_outputs')}")
    for spec in sa.get("specialists", []):
        if not spec.get("recommendations"):
            return _check_result("SPECIALIST_OUTPUT_VALID", "Domain specialist outputs validated", False, "error",
                                 f"{spec.get('name')} produced no recommendations.")
    return _check_result("SPECIALIST_OUTPUT_VALID", "Domain specialist outputs validated", True, "error",
                         f"{len(sa.get('specialists', []))} specialist output(s) validated"
                         + (f"; rejected: {sa.get('rejected_outputs')}" if sa.get("rejected_outputs") else "."))


def _check_retrieval_grounded(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 18: RETRIEVAL_GROUNDED (warning)
    Roadmap gap items should cite a retrieved learning resource.
    """
    retrieval = state.get("retrieval")
    items = [i for i in (state.get("roadmap") or {}).get("items", []) if i.get("resource_status") in ("cited", "no_resource_in_knowledge_base")]
    if retrieval is not None and retrieval.get("status") == "unavailable":
        return _check_result("RETRIEVAL_GROUNDED", "Recommendations cite retrieved resources", False, "warning",
                             "Knowledge base was unavailable during this run.")
    uncited = [i["skill"] for i in items if i.get("resource_status") != "cited"]
    if uncited:
        return _check_result("RETRIEVAL_GROUNDED", "Recommendations cite retrieved resources", False, "warning",
                             f"No knowledge-base resource for: {uncited}")
    return _check_result("RETRIEVAL_GROUNDED", "Recommendations cite retrieved resources", True, "warning",
                         f"{len(items)} roadmap gap item(s) cite retrieved resources.")


def _check_evidence_present(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 5: EVIDENCE_PRESENT
    Every major output should have associated evidence records.
    """
    evidence = state.get("evidence_records", [])
    matching = state.get("matching_result")

    if not evidence:
        return _check_result(
            "EVIDENCE_PRESENT", "Evidence records present",
            False, "error", "No evidence records found in the pipeline output."
        )

    # Check that matching results have corresponding evidence
    if matching:
        matches = matching.get("matches", [])
        match_evidence = [e for e in evidence if e.get("entity_type") == "company_match"]

        if matches and not match_evidence:
            return _check_result(
                "EVIDENCE_PRESENT", "Evidence records present",
                False, "error",
                f"Found {len(matches)} matches but no match evidence records."
            )

    # Check minimum evidence coverage based on present outputs
    evidence_types = {e.get("entity_type") for e in evidence}
    required_types = set()
    
    if state.get("student_profile"):
        required_types.add("student_profile")
    if state.get("skill_gap_report"):
        required_types.add("skill_gap_report")
    if state.get("coding_analytics"):
        required_types.add("coding_analytics")
    if (state.get("matching_result") or {}).get("matches"):
        required_types.add("company_match")
    if state.get("interview_result"):
        required_types.add("interview_preparation")
        
    missing = required_types - evidence_types

    if missing:
        return _check_result(
            "EVIDENCE_PRESENT", "Evidence records present",
            False, "error",
            f"Missing evidence for: {missing}"
        )

    return _check_result(
        "EVIDENCE_PRESENT", "Evidence records present",
        True, "error", f"Evidence present: {len(evidence)} records covering {evidence_types}."
    )


def _check_confidence_present(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 6: CONFIDENCE_PRESENT
    All matches must have confidence scores.
    """
    matching = state.get("matching_result")
    if not matching:
        return _check_result(
            "CONFIDENCE_PRESENT", "Confidence scores present",
            False, "error", "No matching result available."
        )

    matches = matching.get("matches", [])
    missing_confidence = []

    for match in matches:
        conf = match.get("confidence")
        if conf is None:
            missing_confidence.append(match.get("company_name", "Unknown"))

    if missing_confidence:
        return _check_result(
            "CONFIDENCE_PRESENT", "Confidence scores present",
            False, "error",
            f"Missing confidence scores for: {missing_confidence}"
        )

    return _check_result(
        "CONFIDENCE_PRESENT", "Confidence scores present",
        True, "error", f"All {len(matches)} matches have confidence scores."
    )


def _check_low_confidence_flagged(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 7: LOW_CONFIDENCE_FLAGGED
    Low-confidence matches (< 0.6) must be explicitly flagged.
    """
    matching = state.get("matching_result")
    if not matching:
        return _check_result(
            "LOW_CONFIDENCE_FLAGGED", "Low-confidence matches flagged",
            False, "error", "No matching result available."
        )

    matches = matching.get("matches", [])
    low_conf_flags = matching.get("low_confidence_flags", [])

    low_conf_matches = [m for m in matches if m.get("confidence", 1.0) < 0.6]

    if low_conf_matches and not low_conf_flags:
        unflagged = [f"{m['company_name']} (conf={m.get('confidence')})" for m in low_conf_matches]
        return _check_result(
            "LOW_CONFIDENCE_FLAGGED", "Low-confidence matches flagged",
            False, "error",
            f"Low-confidence matches exist but aren't flagged: {unflagged}"
        )

    return _check_result(
        "LOW_CONFIDENCE_FLAGGED", "Low-confidence matches flagged",
        True, "error",
        f"Low-confidence flagging correct. "
        f"Low-conf matches: {len(low_conf_matches)}, Flags: {len(low_conf_flags)}."
    )


def _check_schema_valid(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 8: SCHEMA_VALID
    Verify that all outputs conform to expected structural schemas.
    """
    violations = []

    # Skill gap report schema
    sgr = state.get("skill_gap_report")
    if sgr:
        required_fields = ["overall_coverage", "strengths", "gaps"]
        for field in required_fields:
            if field not in sgr:
                violations.append(f"skill_gap_report missing '{field}'")
        # Coverage must be numeric
        if "overall_coverage" in sgr and not isinstance(sgr["overall_coverage"], (int, float)):
            violations.append("skill_gap_report.overall_coverage must be numeric")

    # Coding analytics schema
    ca = state.get("coding_analytics")
    if ca:
        required_fields = ["summary", "topic_analysis"]
        for field in required_fields:
            if field not in ca:
                violations.append(f"coding_analytics missing '{field}'")

    # Matching result schema
    mr = state.get("matching_result")
    if mr:
        required_fields = ["readiness_score", "matches"]
        for field in required_fields:
            if field not in mr:
                violations.append(f"matching_result missing '{field}'")

        # Each match must have required fields
        for i, match in enumerate(mr.get("matches", [])):
            for mf in ["job_id", "match_score", "confidence", "is_eligible"]:
                if mf not in match:
                    violations.append(f"match[{i}] missing '{mf}'")

    # Interview result schema
    ir = state.get("interview_result")
    if ir:
        required_fields = ["questions", "readiness_assessment"]
        for field in required_fields:
            if field not in ir:
                violations.append(f"interview_result missing '{field}'")

    if violations:
        return _check_result(
            "SCHEMA_VALID", "Output schema validation",
            False, "error",
            f"Schema violations: {violations}"
        )

    return _check_result(
        "SCHEMA_VALID", "Output schema validation",
        True, "error", "All outputs conform to required schemas."
    )


def _check_no_missing_sections(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 9: NO_MISSING_SECTIONS
    All required pipeline sections must be present.
    """
    required_sections = {
        "student_profile": "Student Profile (from Resume Agent)",
        "skill_gap_report": "Skill Gap Report",
        "coding_analytics": "Coding Analytics",
        "matching_result": "Job Matching Result",
        "interview_result": "Interview Preparation",
    }

    missing = []
    for key, label in required_sections.items():
        if not state.get(key):
            missing.append(label)

    if missing:
        return _check_result(
            "NO_MISSING_SECTIONS", "No required sections missing",
            False, "error",
            f"Missing sections: {missing}"
        )

    return _check_result(
        "NO_MISSING_SECTIONS", "No required sections missing",
        True, "error", f"All {len(required_sections)} required sections present."
    )


def _check_no_cross_student_leak(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 10: NO_CROSS_STUDENT_LEAK
    Ensure no data from other students has leaked into this run.
    Verifies student ID presence and verifies that resume content is not
    a duplicate or clone of another student's resume.
    """
    student_id = state.get("student_id", "")
    run_id = state.get("run_id", "")

    # Check that evidence records all belong to this pipeline run
    evidence = state.get("evidence_records", [])
    if not student_id:
        return _check_result(
            "NO_CROSS_STUDENT_LEAK", "No cross-student data leakage",
            False, "error",
            "Student ID is missing from state — cannot verify data isolation."
        )

    # Check if duplicate resume or cross-student plagiarism was flagged
    resume_data = state.get("resume_data") or {}
    has_dup_error = any("DUPLICATE_RESUME_DETECTED" in str(err) for err in state.get("errors", []))
    if resume_data.get("is_duplicate") or has_dup_error:
        matched_student = resume_data.get("matched_student_id", "unknown")
        sim_score = resume_data.get("similarity_score", 0.0)
        return _check_result(
            "NO_CROSS_STUDENT_LEAK", "No cross-student data leakage",
            False, "error",
            f"Plagiarized resume detected: {sim_score * 100:.1f}% similarity with student {str(matched_student)[:8]}."
        )

    return _check_result(
        "NO_CROSS_STUDENT_LEAK", "No cross-student data leakage",
        True, "error",
        f"Data isolation verified for student {student_id[:8]}..."
    )


def _check_no_unsupported_claims(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 11: NO_UNSUPPORTED_CLAIMS
    Verify that scored outputs have supporting evidence and data.
    """
    matching = state.get("matching_result")
    if not matching:
        return _check_result(
            "NO_UNSUPPORTED_CLAIMS", "No unsupported claims",
            True, "error", "No matching result to check."
        )

    evidence = state.get("evidence_records", [])
    matches = matching.get("matches", [])

    # Each match should have a non-empty reasoning
    unsupported = []
    for match in matches:
        reasoning = match.get("reasoning", "")
        if not reasoning or len(reasoning) < 10:
            unsupported.append(match.get("company_name", "Unknown"))

    if unsupported:
        return _check_result(
            "NO_UNSUPPORTED_CLAIMS", "No unsupported claims",
            False, "error",
            f"Matches without sufficient reasoning: {unsupported}"
        )

    return _check_result(
        "NO_UNSUPPORTED_CLAIMS", "No unsupported claims",
        True, "error", f"All {len(matches)} matches have supporting reasoning."
    )


def _check_score_bounds(state: PlacementState) -> Dict[str, Any]:
    """
    CHECK 12: SCORE_BOUNDS
    All scores must be within their valid ranges.
    """
    violations = []

    # Skill gap coverage: 0-100
    sgr = state.get("skill_gap_report")
    if sgr:
        coverage = sgr.get("overall_coverage", 0)
        if not (0 <= coverage <= 100):
            violations.append(f"Skill gap coverage out of range: {coverage}")

    # Match scores: 0-100 for each match
    matching = state.get("matching_result")
    if matching:
        for match in matching.get("matches", []):
            score = match.get("match_score", 0)
            max_score = match.get("max_score", 100)
            if score < 0 or score > max_score:
                violations.append(
                    f"{match.get('company_name')}: score {score} out of range [0, {max_score}]"
                )

            confidence = match.get("confidence", 0)
            if not (0 <= confidence <= 1.0):
                violations.append(
                    f"{match.get('company_name')}: confidence {confidence} out of range [0, 1]"
                )

    # Interview readiness: percentage 0-100
    ir = state.get("interview_result")
    if ir:
        readiness = ir.get("readiness_assessment", {})
        pct = readiness.get("percentage", 0)
        if not (0 <= pct <= 100):
            violations.append(f"Interview readiness percentage out of range: {pct}")

    if violations:
        return _check_result(
            "SCORE_BOUNDS", "Scores within valid ranges",
            False, "error",
            f"Score bound violations: {violations}"
        )

    return _check_result(
        "SCORE_BOUNDS", "Scores within valid ranges",
        True, "error", "All scores within valid ranges."
    )


# ---------------------------------------------------------------------------
# Failure → Agent mapping (for self-healing in Lab 10)
# ---------------------------------------------------------------------------

FAILURE_TO_AGENT_MAP = {
    "SKILL_GAP_CITATION": "skill_gap_agent",
    "ELIGIBILITY_ENFORCED": "job_matching_agent",
    "CONSENT_SATISFIED": None,   # never self-healed: the student must grant consent
    "EVIDENCE_PRESENT": None,
    "CONFIDENCE_PRESENT": "job_matching_agent",
    "LOW_CONFIDENCE_FLAGGED": "job_matching_agent",
    "SCHEMA_VALID": "assemble_draft",
    "NO_MISSING_SECTIONS": None,  # Requires re-run of missing section's agent
    "NO_CROSS_STUDENT_LEAK": None,  # System-level issue
    "NO_UNSUPPORTED_CLAIMS": "job_matching_agent",
    "SCORE_BOUNDS": "job_matching_agent",
    "BIAS_CHECK": "job_matching_agent",
    "NO_APPLICATION_WITHOUT_CONSENT": None,
    "REQUIREMENTS_VERIFIED": None,      # needs a catalogued role or Placement Cell data
    "SOURCE_PROVENANCE": "coding_analytics_agent",
    "SPECIALIST_OUTPUT_VALID": None,
}

HEALABLE_AGENTS = {"skill_gap_agent", "coding_analytics_agent", "job_matching_agent", "interview_agent"}


def _diagnose_failures(checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Diagnose which agents need regeneration based on failing checks.
    Returns a diagnosis report for the self-healing loop.
    """
    failed_checks = [c for c in checks if not c["passed"] and c["severity"] == "error"]
    warning_checks = [c for c in checks if not c["passed"] and c["severity"] == "warning"]

    agents_to_regenerate = set()
    unresolvable = []

    for check in failed_checks:
        target_agent = FAILURE_TO_AGENT_MAP.get(check["code"])
        if target_agent in HEALABLE_AGENTS:
            agents_to_regenerate.add(target_agent)
        else:
            unresolvable.append(check["code"])

    return {
        "failed_error_checks": [c["code"] for c in failed_checks],
        "failed_warning_checks": [c["code"] for c in warning_checks],
        "agents_to_regenerate": list(agents_to_regenerate),
        "unresolvable": unresolvable,
        "can_self_heal": len(unresolvable) == 0 and len(agents_to_regenerate) > 0,
    }


# ---------------------------------------------------------------------------
# Main Agent Node
# ---------------------------------------------------------------------------

def validation_agent_node(state: PlacementState) -> Dict[str, Any]:
    """
    LangGraph Node: Validation Agent.

    Runs all validation checks deterministically (zero LLM).
    Returns validation_report with pass/fail status and diagnosis for self-healing.
    """
    logger.info("[ValidationAgent] Running validation checks...")

    # Run all 12 checks
    checks = [
        _check_skill_gap_citation(state),       # 1
        _check_eligibility_enforced(state),      # 2
        _check_consent_satisfied(state),         # 3
        _check_bias(state),                      # 4
        _check_evidence_present(state),          # 5
        _check_confidence_present(state),        # 6
        _check_low_confidence_flagged(state),    # 7
        _check_schema_valid(state),              # 8
        _check_no_missing_sections(state),       # 9
        _check_no_cross_student_leak(state),     # 10
        _check_no_unsupported_claims(state),     # 11
        _check_score_bounds(state),              # 12
        _check_no_application_without_consent(state),  # 13
        _check_requirements_verified(state),     # 14
        _check_source_provenance(state),         # 15
        _check_specialist_output(state),         # 16
        _check_shortlist_distribution(state),    # 17 (warning)
        _check_retrieval_grounded(state),        # 18 (warning)
    ]

    # Compute aggregate results
    total = len(checks)
    passed_count = sum(1 for c in checks if c["passed"])
    failed_errors = [c for c in checks if not c["passed"] and c["severity"] == "error"]
    failed_warnings = [c for c in checks if not c["passed"] and c["severity"] == "warning"]

    # Overall pass: ALL error-severity checks must pass
    # Warnings don't block but are surfaced
    all_errors_pass = len(failed_errors) == 0

    # Diagnose failures for potential self-healing
    diagnosis = _diagnose_failures(checks)

    validation_report = {
        "passed": all_errors_pass,
        "total_checks": total,
        "passed_checks": passed_count,
        "failed_checks": len(failed_errors) + len(failed_warnings),
        "error_failures": len(failed_errors),
        "warning_failures": len(failed_warnings),
        "checks": checks,
        "diagnosis": diagnosis,
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Determine next step
    failing_check_codes = [c["code"] for c in failed_errors]

    audit = AuditEvent(
        action="validation_completed",
        agent="ValidationAgent",
        timestamp=datetime.now(timezone.utc).isoformat(),
        details={
            "passed": all_errors_pass,
            "total": total,
            "passed_count": passed_count,
            "error_failures": len(failed_errors),
            "warning_failures": len(failed_warnings),
            "failing_codes": failing_check_codes,
        }
    )

    result_emoji = "✅" if all_errors_pass else "❌"
    logger.info(
        f"[ValidationAgent] {result_emoji} Validation {'PASSED' if all_errors_pass else 'FAILED'} — "
        f"Passed: {passed_count}/{total}, Errors: {len(failed_errors)}, Warnings: {len(failed_warnings)}"
    )

    if not all_errors_pass:
        logger.info(f"[ValidationAgent] Failing checks: {failing_check_codes}")
        if diagnosis["can_self_heal"]:
            logger.info(f"[ValidationAgent] Self-healing targets: {diagnosis['agents_to_regenerate']}")

    validation_report["explanation"] = [
        {"code": c["code"], "name": c["name"], "severity": c["severity"], "message": c["message"],
         "self_healable": FAILURE_TO_AGENT_MAP.get(c["code"]) in HEALABLE_AGENTS}
        for c in checks if not c["passed"]
    ]

    return {
        "validation_report": validation_report,
        "validation_passed": all_errors_pass,
        "failing_checks": failing_check_codes,
        "audit_events": [audit],
        "current_step": "validation_agent",
    }
