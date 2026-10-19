"""
Lab 1 planner loop — clarify → plan → revise.

A request is analysed for four slots: target roles, current skill level,
preparation timeline and priorities. Slots already known from the student's
profile are not asked again. A vague request (fewer than two slots resolvable)
therefore always yields at least two clarifying questions. Answers fill slots;
feedback on a draft plan revises it and is recorded in the session history.
"""
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.roles import ROLE_CATALOG, catalog_for_client, domains_for, resolve_role, resolve_targets
from app.core.skills import display_name, find_known_skills

SLOTS = ("target_roles", "skill_level", "timeline", "priorities")
SKILL_LEVELS = ("beginner", "intermediate", "advanced")

QUESTIONS = {
    "target_roles": {
        "id": "target_roles",
        "question": "Which role or career path are you targeting?",
        "help": "Pick one or more, or type your own (e.g. 'Data Analyst', 'MS in Computer Science').",
        "type": "multi_choice",
        "options": [r["title"] for r in catalog_for_client()],
    },
    "skill_level": {
        "id": "skill_level",
        "question": "How would you describe your current skill level or experience for that path?",
        "help": "Beginner: coursework only. Intermediate: projects or an internship. Advanced: substantial work experience.",
        "type": "single_choice",
        "options": ["Beginner", "Intermediate", "Advanced"],
    },
    "timeline": {
        "id": "timeline",
        "question": "What is your preparation timeline?",
        "help": "For example '6 weeks', '3 months', or the date of your target drive.",
        "type": "text",
        "options": [],
    },
    "priorities": {
        "id": "priorities",
        "question": "Which skills or subjects do you want to prioritise?",
        "help": "For example 'DSA, SQL' or 'system design and mock interviews'.",
        "type": "text",
        "options": [],
    },
}

_TIMELINE_RE = re.compile(r"\b(\d{1,2})\s*(weeks?|wks?|months?|mos?)\b", re.IGNORECASE)
_PRIORITY_WORDS = {
    "dsa": "Data Structures", "coding": "Algorithms", "interview": "Mock interviews", "interviews": "Mock interviews",
    "aptitude": "Quantitative Aptitude", "projects": "Projects", "resume": "Resume", "communication": "Communication",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_roles(text: str) -> List[str]:
    """Catalogue roles mentioned in free text (titles or aliases)."""
    if not text:
        return []
    lowered = " " + re.sub(r"[^a-z0-9.+ ]+", " ", text.lower()) + " "
    found: List[str] = []
    for key, meta in ROLE_CATALOG.items():
        names = [meta["title"].lower()] + [a.lower() for a in meta["aliases"]]
        for n in sorted(names, key=len, reverse=True):
            n_clean = re.sub(r"[^a-z0-9.+ ]+", " ", n).strip()
            if len(n_clean) <= 2:
                continue
            if f" {n_clean} " in lowered:
                if key not in found:
                    found.append(key)
                break
    return found


def extract_timeline(text: str) -> Optional[str]:
    m = _TIMELINE_RE.search(text or "")
    if m:
        n = int(m.group(1))
        unit = "weeks" if m.group(2).lower().startswith("w") else "months"
        return f"{n} {unit if n != 1 else unit[:-1]}"
    lowered = (text or "").lower()
    for phrase in ("this semester", "next semester", "this month", "next month", "this year", "next year"):
        if phrase in lowered:
            return phrase
    return None


def extract_skill_level(text: str) -> Optional[str]:
    lowered = (text or "").lower()
    if any(w in lowered for w in ("beginner", "fresher", "no experience", "just started", "basic")):
        return "beginner"
    if "intermediate" in lowered or "some experience" in lowered:
        return "intermediate"
    if "advanced" in lowered or "experienced" in lowered or "expert" in lowered:
        return "advanced"
    return None


def extract_priorities(text: str) -> List[str]:
    out: List[str] = []
    for c in find_known_skills(text or ""):
        name = display_name(c)
        if name not in out:
            out.append(name)
    lowered = (text or "").lower()
    for word, label in _PRIORITY_WORDS.items():
        if re.search(rf"\b{word}\b", lowered) and label not in out:
            out.append(label)
    return out


def analyze_request(text: str, prefs: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Return (slots, provenance) where provenance says where each slot came from."""
    prefs = prefs or {}
    slots: Dict[str, Any] = {}
    prov: Dict[str, str] = {}

    roles = extract_roles(text)
    if roles:
        slots["target_roles"], prov["target_roles"] = roles, "request"
    elif prefs.get("target_roles"):
        slots["target_roles"], prov["target_roles"] = list(prefs["target_roles"]), "profile"

    timeline = extract_timeline(text)
    if timeline:
        slots["timeline"], prov["timeline"] = timeline, "request"
    elif prefs.get("timeline"):
        slots["timeline"], prov["timeline"] = prefs["timeline"], "profile"

    level = extract_skill_level(text)
    if level:
        slots["skill_level"], prov["skill_level"] = level, "request"
    elif prefs.get("skill_level"):
        slots["skill_level"], prov["skill_level"] = prefs["skill_level"], "profile"

    priorities = extract_priorities(text)
    if priorities:
        slots["priorities"], prov["priorities"] = priorities, "request"
    elif prefs.get("priorities"):
        slots["priorities"], prov["priorities"] = list(prefs["priorities"]), "profile"

    for k in ("preferred_domains", "career_goal", "interests"):
        if prefs.get(k):
            slots[k] = prefs[k]
    return slots, prov


def missing_slots(slots: Dict[str, Any]) -> List[str]:
    return [s for s in SLOTS if not slots.get(s)]


def questions_for(missing: List[str]) -> List[Dict[str, Any]]:
    return [dict(QUESTIONS[s]) for s in missing]


def apply_answer(slots: Dict[str, Any], slot: str, answer: Any) -> Optional[str]:
    """Fill one slot from an answer. Returns an error message if the answer cannot be used."""
    if slot not in SLOTS:
        return f"Unknown question '{slot}'"
    if answer is None or (isinstance(answer, str) and not answer.strip()) or (isinstance(answer, list) and not answer):
        return "Answer is empty"
    if slot == "target_roles":
        values = answer if isinstance(answer, list) else re.split(r"[,;/]| and ", str(answer))
        roles = []
        for v in values:
            v = str(v).strip()
            if not v:
                continue
            roles.append(resolve_role(v) or v)  # unresolved titles are kept as custom roles
        if not roles:
            return "Could not read any role"
        slots["target_roles"] = list(dict.fromkeys(roles))
    elif slot == "skill_level":
        level = str(answer).strip().lower()
        if level not in SKILL_LEVELS:
            level = extract_skill_level(level) or ""
        if level not in SKILL_LEVELS:
            return "Choose beginner, intermediate or advanced"
        slots["skill_level"] = level
    elif slot == "timeline":
        tl = extract_timeline(str(answer)) or str(answer).strip()[:60]
        slots["timeline"] = tl
    elif slot == "priorities":
        values = answer if isinstance(answer, list) else re.split(r"[,;]| and ", str(answer))
        pr = []
        for v in values:
            v = str(v).strip()
            if v:
                found = extract_priorities(v)
                pr.extend(found or [v[:60]])
        slots["priorities"] = list(dict.fromkeys(pr))
    return None


def _weeks(timeline: Optional[str]) -> Optional[int]:
    if not timeline:
        return None
    m = _TIMELINE_RE.search(timeline)
    if not m:
        return {"this month": 4, "next month": 8, "this semester": 16, "next semester": 24,
                "this year": 40, "next year": 52}.get(timeline.lower())
    n = int(m.group(1))
    return n * 4 if m.group(2).lower().startswith("m") else n


def build_plan(slots: Dict[str, Any]) -> Dict[str, Any]:
    targets = resolve_targets(slots.get("target_roles") or [])
    weeks = _weeks(slots.get("timeline")) or 12
    level = slots.get("skill_level", "beginner")
    priorities = slots.get("priorities") or []
    # Phase lengths scale with the timeline; beginners get a longer foundation phase
    foundation = max(1, round(weeks * (0.4 if level == "beginner" else 0.3)))
    practice = max(1, round(weeks * 0.35))
    apply_phase = max(1, weeks - foundation - practice)
    steps = [
        {"phase": 1, "title": "Assess readiness", "weeks": "Week 1",
         "detail": "Run the readiness analysis on your resume and consented coding profiles to get verified gaps."},
        {"phase": 2, "title": "Close priority gaps", "weeks": f"Weeks 1–{foundation}",
         "detail": f"Focus first on: {', '.join(priorities) if priorities else 'the critical gaps from your analysis'}."},
        {"phase": 3, "title": "Practice and mock interviews", "weeks": f"Weeks {foundation + 1}–{foundation + practice}",
         "detail": "Timed problem practice and mock interviews targeting your gap skills."},
        {"phase": 4, "title": "Apply and iterate", "weeks": f"Weeks {foundation + practice + 1}–{foundation + practice + apply_phase}",
         "detail": "Apply to matched drives (you submit applications yourself) and refresh the analysis."},
    ]
    return {
        "target_roles": [t["role_key"] or t["title"] for t in targets],
        "target_role_details": targets,
        "unresolved_roles": [t["title"] for t in targets if not t["role_key"]],
        "domains": domains_for(targets, slots.get("preferred_domains")),
        "skill_level": level,
        "timeline": slots.get("timeline"),
        "timeline_weeks": weeks,
        "priorities": priorities,
        "career_goal": slots.get("career_goal"),
        "steps": steps,
        "built_at": _now(),
    }


_REPLACE_RE = re.compile(r"\b(instead|switch(ed)? to|change (it|my role|the role)? ?to|only)\b", re.IGNORECASE)
_REMOVE_RE = re.compile(r"\b(remove|drop|not|no longer|without)\s+([a-z0-9 .+/]+)", re.IGNORECASE)


def revise_plan(slots: Dict[str, Any], feedback: str) -> Tuple[Dict[str, Any], List[str]]:
    """Apply student feedback to the slots. Returns (slots, list of human-readable changes)."""
    changes: List[str] = []
    new = {k: (list(v) if isinstance(v, list) else v) for k, v in slots.items()}

    removed = []
    for m in _REMOVE_RE.finditer(feedback):
        for key in extract_roles(m.group(2)):
            if key in (new.get("target_roles") or []):
                new["target_roles"].remove(key)
                removed.append(ROLE_CATALOG[key]["title"])
    if removed:
        changes.append(f"Removed target role(s): {', '.join(removed)}")

    roles = [r for r in extract_roles(feedback) if ROLE_CATALOG[r]["title"] not in removed]
    if roles:
        if _REPLACE_RE.search(feedback):
            new["target_roles"] = roles
            changes.append(f"Target role(s) set to: {', '.join(ROLE_CATALOG[r]['title'] for r in roles)}")
        else:
            added = [r for r in roles if r not in (new.get("target_roles") or [])]
            if added:
                new["target_roles"] = (new.get("target_roles") or []) + added
                changes.append(f"Added target role(s): {', '.join(ROLE_CATALOG[r]['title'] for r in added)}")

    tl = extract_timeline(feedback)
    if tl and tl != new.get("timeline"):
        new["timeline"] = tl
        changes.append(f"Timeline changed to {tl}")

    level = extract_skill_level(feedback)
    if level and level != new.get("skill_level"):
        new["skill_level"] = level
        changes.append(f"Skill level changed to {level}")

    pr = [p for p in extract_priorities(feedback) if p not in (new.get("priorities") or [])]
    if pr and not roles:
        new["priorities"] = (new.get("priorities") or []) + pr
        changes.append(f"Added priorities: {', '.join(pr)}")

    if not new.get("target_roles"):
        return slots, ["Feedback would remove every target role — keep at least one."]
    return new, changes
