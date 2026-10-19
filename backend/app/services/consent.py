"""
Source-specific consent (Chapter 9: "explicit consent per source").

Each source has its own row in the `consents` table. A source counts as granted
only if its row exists with granted=True; a missing row or a revoked row is
never treated as granted.
"""
from typing import Any, Dict, Iterable

CONSENT_SOURCES: Dict[str, Dict[str, Any]] = {
    "resume_processing": {"label": "Analyse my uploaded resume", "required": True},
    "github": {"label": "Read my public GitHub profile", "required": False},
    "leetcode": {"label": "Read my public LeetCode profile", "required": False},
    "academic_records": {"label": "Use my CGPA for eligibility checks", "required": False},
}

REQUIRED_SOURCES = [k for k, v in CONSENT_SOURCES.items() if v["required"]]


def consent_status(records: Iterable[Any]) -> Dict[str, Dict[str, Any]]:
    """Build {source: {status, granted_at, revoked_at}} from Consent rows."""
    by_type = {r.consent_type: r for r in records}
    out = {}
    for source in CONSENT_SOURCES:
        r = by_type.get(source)
        if r is None:
            status = "missing"
        elif r.granted:
            status = "granted"
        else:
            status = "revoked" if r.revoked_at else "missing"
        out[source] = {
            "status": status,
            "granted_at": r.granted_at.isoformat() if r is not None and r.granted_at else None,
            "revoked_at": r.revoked_at.isoformat() if r is not None and r.revoked_at else None,
        }
    return out


def missing_required(status: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    return {s: (status.get(s) or {}).get("status", "missing")
            for s in REQUIRED_SOURCES if (status.get(s) or {}).get("status") != "granted"}


def is_granted(status: Dict[str, Dict[str, Any]], source: str) -> bool:
    return (status.get(source) or {}).get("status") == "granted"
