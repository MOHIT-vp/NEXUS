"""
Coding Analytics Agent (A3) — aggregates the student's own coding-platform activity.

Architecture contract:
- Input: student_id, consent snapshot
- Data: CodingConnector via the hub — GitHub REST API and LeetCode GraphQL for
  the handles on the student's profile, only when that source's consent is granted
- Output: per-source status (ok / not_consented / not_configured / not_found /
  rate_limited / unavailable / invalid_handle) with retrieval time and freshness,
  plus deterministic statistics computed only from sources that returned data
- Guardrails: pull only from authorised integrations; keep raw submissions private
  (only aggregates are stored); surface trends rather than raw scores; never
  substitute fixture data when a source is missing
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import logging
import math

from app.agents.llm import get_chat_model
from app.agents.state import AuditEvent, PlacementState
from app.config import settings
from app.connectors.hub import HubUnavailableError, get_hub
from app.schemas.evidence import EvidenceRecord

logger = logging.getLogger(__name__)

SOURCE_LABELS = {"github": "GitHub", "leetcode": "LeetCode"}


# ---------------------------------------------------------------------------
# Deterministic computation functions
# ---------------------------------------------------------------------------

def _compute_difficulty_score(distribution: Dict[str, int]) -> float:
    """Weighted difficulty score (0-100): Easy=1x, Medium=2x, Hard=4x."""
    easy = distribution.get("easy", 0)
    medium = distribution.get("medium", 0)
    hard = distribution.get("hard", 0)
    total = easy + medium + hard
    if total == 0:
        return 0.0
    weighted = easy + medium * 2 + hard * 4
    return round(weighted / (total * 4) * 100, 1)


def _compute_activity_trend(monthly_data: List[Dict[str, Any]]) -> str:
    """Linear-regression slope over the last 6 months: improving / stable / declining."""
    if len(monthly_data) < 3:
        return "insufficient_data"
    recent = monthly_data[-6:]
    n = len(recent)
    values = [m.get("problems_solved", m.get("submissions", 0)) for m in recent]
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    if den == 0:
        return "stable"
    slope = num / den
    if slope > 2:
        return "improving"
    if slope < -2:
        return "declining"
    return "stable"


def _compute_topic_strengths(topics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Classify topic strength. When the platform reports accuracy it is combined with
    volume; LeetCode's public API exposes solved counts only, so volume alone is used.
    """
    results = []
    for topic in topics:
        solved = topic.get("solved", 0)
        accuracy = topic.get("accuracy")
        if accuracy is not None:
            strength_score = round(math.sqrt(solved) * (accuracy / 100), 2)
            if accuracy >= 85 and solved >= 15:
                level = "strong"
            elif accuracy >= 75 and solved >= 10:
                level = "competent"
            elif accuracy >= 60 and solved >= 5:
                level = "developing"
            else:
                level = "needs_work"
        else:
            strength_score = round(math.sqrt(solved), 2)
            level = "strong" if solved >= 40 else "competent" if solved >= 20 else "developing" if solved >= 8 else "needs_work"
        results.append({
            "topic": topic["topic"],
            "solved": solved,
            "total_attempted": topic.get("total_attempted"),
            "accuracy": accuracy,
            "tier": topic.get("tier"),
            "strength_score": strength_score,
            "strength_level": level,
        })
    results.sort(key=lambda x: x["strength_score"], reverse=True)
    return results


def _compute_percentile_estimate(total_solved: int, contest_rating: int, difficulty_score: float) -> float:
    """
    Derived 0-100 coding index (NOT a platform percentile): volume (30), contest
    rating (40) and difficulty mix (30). Reported as `coding_index`.
    """
    volume = min(total_solved / 500, 1.0) * 30
    rating = min((contest_rating or 0) / 2500, 1.0) * 40
    difficulty = (difficulty_score / 100) * 30
    return round(volume + rating + difficulty, 1)


def _freshness(retrieved_at: Optional[str]) -> str:
    if not retrieved_at:
        return "unknown"
    try:
        ts = datetime.fromisoformat(retrieved_at)
    except ValueError:
        return "unknown"
    age = datetime.now(timezone.utc) - ts
    if age <= timedelta(hours=settings.CODING_DATA_STALE_HOURS):
        return "fresh"
    return "stale"


def summarize_sources(sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Pure function: build the coding analytics section from connector results."""
    lc = next((s for s in sources if s["source"] == "leetcode" and s["status"] == "ok" and s.get("data")), None)
    gh = next((s for s in sources if s["source"] == "github" and s["status"] == "ok" and s.get("data")), None)

    summary: Dict[str, Any] = {"data_available": bool(lc or gh), "sources_ok": [s["source"] for s in (lc, gh) if s]}
    topic_analysis: List[Dict[str, Any]] = []
    monthly: List[Dict[str, Any]] = []
    languages: Dict[str, int] = {}

    if lc:
        d = lc["data"]
        dist = d.get("difficulty_distribution", {})
        difficulty_score = _compute_difficulty_score(dist)
        monthly = [{"month": m["month"], "problems_solved": m["submissions"], "unit": "accepted+attempted submissions"}
                   for m in d.get("monthly_activity", [])]
        contest = d.get("contest") or {}
        top_pct = contest.get("top_percentage")
        summary.update({
            "total_solved": d.get("total_solved", 0),
            "difficulty_distribution": dist,
            "difficulty_score": difficulty_score,
            "contest_rating": contest.get("rating"),
            "contest_count": contest.get("attended", 0),
            "contest_global_ranking": contest.get("global_ranking"),
            # Platform-reported contest percentile (higher is better); None if no contests
            "coding_percentile": round(100 - float(top_pct), 1) if top_pct is not None else None,
            "coding_index": _compute_percentile_estimate(d.get("total_solved", 0), contest.get("rating") or 0, difficulty_score),
            "coding_index_note": "Derived index from solved volume, contest rating and difficulty mix; not a platform percentile.",
            "activity_trend": _compute_activity_trend(monthly),
            "streak_days": d.get("streak_days", 0),
            "active_days": d.get("active_days", 0),
        })
        topic_analysis = _compute_topic_strengths(d.get("topics", []))
        languages = d.get("languages", {})

    if gh:
        d = gh["data"]
        summary["github"] = {
            "public_repos": d.get("public_repos", 0),
            "original_repos": d.get("original_repos", 0),
            "recently_active_repos": d.get("recently_active_repos", 0),
            "last_push_at": d.get("last_push_at"),
            "top_languages": list((d.get("languages") or {}).keys())[:5],
            "followers": d.get("followers", 0),
        }
        if not languages:
            languages = d.get("languages", {})
        if not lc:
            summary["activity_trend"] = _compute_activity_trend(
                [{"problems_solved": m["repos_pushed"]} for m in d.get("repo_activity_by_month", [])])

    if languages:
        summary["primary_language"] = max(languages.items(), key=lambda kv: kv[1])[0]

    status = "ok" if (lc and gh) else "partial" if (lc or gh) else "unavailable"
    return {
        "status": status,
        "summary": summary,
        "topic_analysis": topic_analysis,
        "monthly_activity": monthly,
        "languages_used": languages,
        "platform": ", ".join(SOURCE_LABELS[s["source"]] for s in (lc, gh) if s) or None,
    }


def _deterministic_narration(section: Dict[str, Any], sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = section["summary"]
    if not summary.get("data_available"):
        reasons = "; ".join(f"{SOURCE_LABELS[s['source']]}: {s['status'].replace('_', ' ')}" for s in sources)
        return {
            "overall_assessment": f"No coding-platform data is available ({reasons}). Coding activity is excluded from scoring.",
            "trend_analysis": "Not available.",
            "key_strengths": [],
            "improvement_areas": [],
            "recommendations": ["Add your GitHub and/or LeetCode handle in your profile and grant consent to include coding activity."],
        }
    topics = section["topic_analysis"]
    strong = [t["topic"] for t in topics if t["strength_level"] in ("strong", "competent")][:3]
    weak = [t["topic"] for t in sorted(topics, key=lambda t: t["solved"]) if t["strength_level"] in ("needs_work", "developing")][:3]
    parts = []
    if "total_solved" in summary:
        parts.append(f"{summary['total_solved']} problems solved on LeetCode "
                     f"(easy {summary['difficulty_distribution'].get('easy', 0)}, medium {summary['difficulty_distribution'].get('medium', 0)}, "
                     f"hard {summary['difficulty_distribution'].get('hard', 0)})")
    if summary.get("github"):
        g = summary["github"]
        parts.append(f"{g['original_repos']} original public GitHub repositories, {g['recently_active_repos']} active in the last 90 days")
    recs = []
    if weak:
        recs.append(f"Practise {weak[0]} problems — it is one of your least-solved topics.")
    if summary.get("difficulty_distribution", {}).get("hard", 0) < 10 and "total_solved" in summary:
        recs.append("Attempt more Hard problems to strengthen the difficulty mix.")
    if summary.get("contest_count", 0) == 0 and "total_solved" in summary:
        recs.append("Take part in LeetCode contests to obtain a contest rating.")
    if summary.get("github") and summary["github"]["recently_active_repos"] == 0:
        recs.append("Push recent work to GitHub so reviewers can see current activity.")
    return {
        "overall_assessment": "; ".join(parts) + ".",
        "trend_analysis": f"Activity trend: {summary.get('activity_trend', 'insufficient_data').replace('_', ' ')}.",
        "key_strengths": strong,
        "improvement_areas": weak,
        "recommendations": recs or ["Maintain your current practice pace."],
    }


def coding_analytics_agent_node(state: PlacementState) -> Dict[str, Any]:
    """LangGraph node: Coding Analytics Agent."""
    if not state.get("consent_validated", False):
        return {"errors": ["CodingAnalyticsAgent: Consent not validated. Cannot access coding data."]}

    student_id = state.get("student_id", "")
    try:
        hub = get_hub(state)
    except HubUnavailableError as exc:
        return {"errors": [f"CodingAnalyticsAgent: {exc}"]}

    handles = state.get("platform_handles") or {}
    sources = []
    for platform in ("leetcode", "github"):
        result = hub.coding_platform(student_id, platform, handles.get(platform))
        ok = result["status"] == "ok"
        sources.append({
            "source": platform,
            "label": SOURCE_LABELS[platform],
            "status": result["status"],
            "retrieved_at": result.get("retrieved_at") if ok else None,
            "freshness": _freshness(result.get("retrieved_at")) if ok else None,
            "from_cache": result.get("from_cache", False),
            "source_url": result.get("source_url"),
            "error": result.get("error"),
            "data": result.get("data") if ok else None,
        })

    section = summarize_sources(sources)
    narration = _deterministic_narration(section, sources)
    narration_method = "deterministic"
    llm = get_chat_model(temperature=0.3)
    if llm is not None and section["summary"].get("data_available"):
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            msg = llm.invoke([
                SystemMessage(content="Summarise these pre-computed coding statistics in two sentences. "
                                      "Use only the numbers given; do not invent statistics."),
                HumanMessage(content=str(section["summary"])),
            ])
            text = getattr(msg, "content", "")
            if isinstance(text, str) and text.strip():
                narration["overall_assessment"] = "[AI-generated summary] " + text.strip()[:600]
                narration_method = "llm"
        except Exception as exc:
            logger.warning(f"[CodingAnalyticsAgent] narration unavailable: {exc}")

    coding_analytics = {
        **section,
        "sources": sources,
        "narration": narration,
        "narration_method": narration_method,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    evidence = []
    for s in sources:
        evidence.append(EvidenceRecord(
            entity_type="coding_analytics",
            evidence_type="platform_api" if s["status"] == "ok" else "source_unavailable",
            source=f"{s['label']} ({s['source_url'] or 'no profile URL'})",
            content=(f"{s['label']}: status={s['status']}"
                     + (f", retrieved {s['retrieved_at']}{' (cached)' if s['from_cache'] else ''}" if s["status"] == "ok" else
                        f", reason: {s['error'] or 'n/a'}")),
            scope_tags=["coding", s["source"], s["status"]],
        ).model_dump())

    audit = AuditEvent(action="coding_analytics_computed", agent="CodingAnalyticsAgent",
                       timestamp=datetime.now(timezone.utc).isoformat(),
                       details={"source_status": {s["source"]: s["status"] for s in sources},
                                "status": section["status"]})

    return {"coding_analytics": coding_analytics, "evidence_records": evidence, "audit_events": [audit]}
