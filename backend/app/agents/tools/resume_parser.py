"""
Deterministic resume parser (used when no LLM is configured, or if LLM extraction fails).

It extracts only what is literally present in the text: skills from a known
vocabulary, project/experience entries from their sections, degree and CGPA.
Proficiency is inferred from evidence, not guessed:

    beginner      — skill only listed
    intermediate  — skill also used in at least one project or role
    advanced      — skill used in three or more projects/roles

Every skill carries the evidence lines it was found in.
"""
import re
from typing import Any, Dict, List, Optional

from app.core.skills import canonical, display_name, find_known_skills

SECTION_PATTERNS = {
    "summary": r"(professional\s+)?summary|objective|profile|about\s+me",
    "skills": r"(technical\s+|key\s+|core\s+)?skills|technologies|tech\s+stack|tools(\s+and\s+technologies)?|competencies",
    "projects": r"(academic\s+|personal\s+|key\s+)?projects?",
    "experience": r"(work\s+|professional\s+)?experience|internships?|employment(\s+history)?",
    "education": r"education|academics?|academic\s+(details|qualifications?)|qualifications?",
    "other": r"certifications?|achievements?|awards|publications|extra[- ]?curricular|activities|interests|hobbies|languages|references|declaration",
}

_HEADING_RE = {
    name: re.compile(rf"^\s*(?:{pat})\s*[:\-–]?\s*$", re.IGNORECASE) for name, pat in SECTION_PATTERNS.items()
}

DEGREE_RE = re.compile(
    r"\b(B\.?\s?Tech|B\.?\s?E\.?|B\.?\s?Sc|BCA|M\.?\s?Tech|M\.?\s?E\.?|M\.?\s?Sc|MCA|MBA|Ph\.?\s?D|Diploma|Bachelor[^\n,]{0,40}|Master[^\n,]{0,40})",
    re.IGNORECASE,
)
CGPA_RE = re.compile(r"\b(?:c\.?g\.?p\.?a|g\.?p\.?a|cpi|sgpa)\b[^0-9\n]{0,12}(\d{1,2}(?:\.\d{1,2})?)\s*(?:/\s*(10|4)(?:\.0+)?)?", re.IGNORECASE)
BULLET_RE = re.compile(r"^\s*([\-•●▪◦*·]|\d+[.)])\s+")


def _clean(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text or "")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def split_sections(text: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {"header": []}
    current = "header"
    for raw in _clean(text).split("\n"):
        line = raw.strip()
        if not line:
            continue
        matched = None
        if len(line) <= 45:
            for name, rx in _HEADING_RE.items():
                if rx.match(line):
                    matched = name
                    break
        if matched:
            current = matched
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _entries(lines: List[str]) -> List[List[str]]:
    """Group a section's lines into entries: a non-bullet line starts a new entry."""
    entries: List[List[str]] = []
    for line in lines:
        if BULLET_RE.match(line) and entries:
            entries[-1].append(BULLET_RE.sub("", line))
        elif not entries or (not BULLET_RE.match(line) and len(line) < 120 and not line.endswith(".")):
            entries.append([BULLET_RE.sub("", line)])
        else:
            entries[-1].append(line)
    return [e for e in entries if e]


def _parse_education(lines: List[str], full_text: str) -> Optional[Dict[str, Any]]:
    blob = "\n".join(lines) if lines else full_text
    degree = DEGREE_RE.search(blob)
    gpa = None
    m = CGPA_RE.search(blob) or CGPA_RE.search(full_text)
    if m:
        value = float(m.group(1))
        scale = float(m.group(2)) if m.group(2) else 10.0
        if scale == 4.0 and value <= 4.0:
            value = round(value * 2.5, 2)
        if 0 < value <= 10:
            gpa = value
    institution = None
    for line in lines:
        if re.search(r"(university|institute|college|iit|nit|iiit|school)", line, re.IGNORECASE):
            institution = line[:150]
            break
    if not degree and gpa is None and not institution:
        return None
    return {"degree": degree.group(1).strip() if degree else None, "institution": institution, "gpa": gpa}


def parse_resume_text(text: str) -> Dict[str, Any]:
    text = _clean(text)
    sections = split_sections(text)

    skills_lines = sections.get("skills", [])
    listed: Dict[str, List[str]] = {}
    for line in skills_lines:
        body = line.split(":", 1)[1] if ":" in line[:40] else line
        for c in find_known_skills(body, explicit_list=True):
            listed.setdefault(c, []).append(f"Skills section: {line[:120]}")
        # Also accept comma separated tokens that are not in the vocabulary
        for token in re.split(r"[,;|/]", body):
            tok = token.strip(" .•-")
            if 1 < len(tok) <= 30 and re.match(r"^[A-Za-z][A-Za-z0-9+#.\- ]*$", tok) and len(tok.split()) <= 3:
                listed.setdefault(canonical(tok), []).append(f"Skills section: {line[:120]}")

    projects = []
    for entry in _entries(sections.get("projects", [])):
        blob = " ".join(entry)
        techs = find_known_skills(blob)
        projects.append({
            "title": entry[0][:150],
            "description": " ".join(entry[1:])[:600],
            "technologies": [display_name(t) for t in techs],
        })

    experiences = []
    for entry in _entries(sections.get("experience", [])):
        head = entry[0]
        parts = re.split(r"\s[\-–|@,]\s|\sat\s", head, maxsplit=1)
        experiences.append({
            "company": parts[1].strip()[:150] if len(parts) > 1 else head[:150],
            "role": parts[0].strip()[:150],
            "duration": (re.search(r"((?:19|20)\d{2}.{0,20}(?:(?:19|20)\d{2}|present|current))", " ".join(entry), re.IGNORECASE) or [None])[0] or "",
            "description": " ".join(entry[1:])[:600],
            "technologies": [display_name(t) for t in find_known_skills(" ".join(entry))],
        })

    usage: Dict[str, List[str]] = {}
    for p in projects:
        for t in p["technologies"]:
            usage.setdefault(canonical(t), []).append(f"Project: {p['title'][:80]}")
    for e in experiences:
        for t in e["technologies"]:
            usage.setdefault(canonical(t), []).append(f"Experience: {e['role'][:60]} @ {e['company'][:60]}")

    # Free-text mentions anywhere else (summary, header) count as listed
    for c in find_known_skills(" ".join(sections.get("summary", []))):
        listed.setdefault(c, []).append("Summary")

    all_skills = set(listed) | set(usage)
    skills = []
    for c in sorted(all_skills):
        if not c:
            continue
        uses = usage.get(c, [])
        level = "advanced" if len(uses) >= 3 else "intermediate" if uses else "beginner"
        skills.append({
            "name": display_name(c),
            "proficiency": level,
            "evidence": list(dict.fromkeys(listed.get(c, []) + uses))[:6],
            "source": "resume",
        })

    summary_lines = sections.get("summary", [])
    summary = " ".join(summary_lines)[:600] if summary_lines else None

    return {
        "summary": summary,
        "skills": skills,
        "projects": projects,
        "experiences": experiences,
        "education": _parse_education(sections.get("education", []), text),
        "years_experience": 0,
        "sections_found": [k for k in sections if k != "header" and sections[k]],
    }
