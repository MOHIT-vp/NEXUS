"""
Target-role catalogue.

Maps the roles students can target to (a) the role_family key used by the
skill-benchmark library and job listings and (b) the domain specialist(s)
(Lab 13) responsible for that role. Free-text targets are resolved through
aliases; anything unresolved is kept as a custom role and matched against job
titles in the database — it is never silently replaced with a default.
"""
import re
from typing import Dict, List, Optional

ROLE_CATALOG: Dict[str, Dict] = {
    "software_engineer": {
        "title": "Software Engineer",
        "domains": ["software"],
        "job_families": ["software_engineering"],
        "aliases": ["sde", "software developer", "software engineer", "swe", "programmer", "full stack", "full stack developer"],
    },
    "backend_developer": {
        "title": "Backend Developer",
        "domains": ["software"],
        "job_families": ["software_engineering", "backend"],
        "aliases": ["backend", "backend engineer", "api developer", "server side developer"],
    },
    "frontend_developer": {
        "title": "Frontend Developer",
        "domains": ["software"],
        "job_families": ["software_engineering", "frontend"],
        "aliases": ["frontend", "front end", "ui developer", "react developer", "web developer"],
    },
    "devops_engineer": {
        "title": "DevOps / Cloud Engineer",
        "domains": ["software"],
        "job_families": ["devops", "cloud"],
        "aliases": ["devops", "cloud engineer", "sre", "site reliability", "platform engineer"],
    },
    "data_analyst": {
        "title": "Data Analyst",
        "domains": ["analytics"],
        "job_families": ["analytics", "data_analytics"],
        "aliases": ["data analyst", "business analyst", "bi analyst", "analytics"],
    },
    "data_engineer": {
        "title": "Data Engineer",
        "domains": ["analytics", "software"],
        "job_families": ["data_engineering", "analytics"],
        "aliases": ["data engineer", "etl developer", "big data engineer"],
    },
    "ml_engineer": {
        "title": "Machine Learning Engineer",
        "domains": ["analytics", "software"],
        "job_families": ["machine_learning", "analytics"],
        "aliases": ["ml engineer", "machine learning", "ai engineer", "data scientist", "data science"],
    },
    "embedded_engineer": {
        "title": "Embedded Systems Engineer",
        "domains": ["core", "software"],
        "job_families": ["core", "embedded"],
        "aliases": ["embedded", "embedded systems", "firmware", "vlsi", "electronics engineer"],
    },
    "mechanical_design_engineer": {
        "title": "Mechanical Design Engineer",
        "domains": ["core"],
        "job_families": ["core", "mechanical"],
        "aliases": ["mechanical", "design engineer", "cad engineer", "mechanical engineer", "core engineering"],
    },
    "higher_studies_research": {
        "title": "Higher Studies (MS / M.Tech / PhD)",
        "domains": ["higher_studies"],
        "job_families": ["higher_studies"],
        "aliases": ["higher studies", "ms", "masters", "m.tech", "mtech", "phd", "research", "gate", "gre"],
    },
}

DOMAIN_LABELS = {
    "software": "Software Engineering",
    "analytics": "Data & Analytics",
    "core": "Core Engineering",
    "higher_studies": "Higher Studies",
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9.+ ]+", " ", text.lower()).strip()


def resolve_role(text: str) -> Optional[str]:
    """Resolve a role key or free-text title to a catalogue key, or None."""
    if not text:
        return None
    raw = text.strip()
    if raw in ROLE_CATALOG:
        return raw
    norm = _norm(raw.replace("_", " "))
    for key, meta in ROLE_CATALOG.items():
        if norm == _norm(meta["title"]) or norm == _norm(key.replace("_", " ")):
            return key
    for key, meta in ROLE_CATALOG.items():
        if any(norm == _norm(a) for a in meta["aliases"]):
            return key
    for key, meta in ROLE_CATALOG.items():
        if any(re.search(rf"\b{re.escape(_norm(a))}\b", norm) for a in meta["aliases"] if len(a) > 3):
            return key
    return None


def resolve_targets(targets: List[str]) -> List[Dict]:
    """
    Resolve a list of target-role strings. Returns entries:
        {"input": str, "role_key": str|None, "title": str, "domains": [...], "job_families": [...]}
    Custom roles keep their own title and have no domains until a specialist is chosen.
    """
    out, seen = [], set()
    for t in targets or []:
        if not t or not str(t).strip():
            continue
        key = resolve_role(str(t))
        ident = key or _norm(str(t))
        if ident in seen:
            continue
        seen.add(ident)
        if key:
            meta = ROLE_CATALOG[key]
            out.append({"input": t, "role_key": key, "title": meta["title"],
                        "domains": list(meta["domains"]), "job_families": list(meta["job_families"])})
        else:
            out.append({"input": t, "role_key": None, "title": str(t).strip(), "domains": [], "job_families": []})
    return out


def domains_for(targets: List[Dict], preferred_domains: Optional[List[str]] = None) -> List[str]:
    """Ordered, de-duplicated specialist domains for the resolved targets plus explicit preferences."""
    ordered: List[str] = []
    for t in targets:
        for d in t.get("domains", []):
            if d not in ordered:
                ordered.append(d)
    for d in preferred_domains or []:
        if d in DOMAIN_LABELS and d not in ordered:
            ordered.append(d)
    return ordered


def catalog_for_client() -> List[Dict]:
    return [
        {"role_key": k, "title": v["title"], "domains": v["domains"]}
        for k, v in ROLE_CATALOG.items()
    ]
