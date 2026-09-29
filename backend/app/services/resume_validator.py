"""
Resume Validator & Duplicate Detection Service.

Implements multi-tiered, name-agnostic resume plagiarism and duplicate detection.
When a student uploads a resume, this service verifies that the content has not
previously been uploaded by another student (catching clones where only the name,
contact details, or minor cosmetic elements were modified).
"""
import difflib
import hashlib
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import Resume
from app.models.user import Student, User
from app.agents.tools.resume_tools import extract_text_from_file

logger = logging.getLogger(__name__)

# Configurable thresholds
DUPLICATE_SIMILARITY_THRESHOLD = 0.70  # >= 70% content similarity flagged as duplicate/clone
SUSPICIOUS_SIMILARITY_THRESHOLD = 0.50  # >= 50% flagged as suspicious for manual review
MIN_SUBSTANTIVE_BULLET_LEN = 25  # Minimum character length for a distinct bullet/claim
NGRAM_SIZE = 3  # Word 3-grams for shingling
MIN_TEXT_WORDS_FOR_COMPARISON = 15  # Minimum word count required to declare text similarity duplicate


class ResumeVerificationResult(BaseModel):
    """Result of resume duplicate / plagiarism verification."""
    is_duplicate: bool = Field(description="True if flagged as a clone/plagiarized resume from another student.")
    confidence: str = Field(description="'high', 'medium', or 'none'")
    similarity_score: float = Field(description="Normalized similarity score [0.0, 1.0]")
    matched_resume_id: Optional[uuid.UUID] = None
    matched_student_id: Optional[uuid.UUID] = None
    matched_student_name: Optional[str] = None
    matched_file_name: Optional[str] = None
    metrics: Dict[str, float] = Field(default_factory=dict)
    reasons: List[str] = Field(default_factory=list)
    matching_snippets: List[str] = Field(default_factory=list)
    status: str = Field(default="verified")  # 'verified', 'flagged_duplicate', 'suspicious'


# ---------------------------------------------------------------------------
# Preprocessing and Personal Identifier Masking
# ---------------------------------------------------------------------------

EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
PHONE_REGEX = re.compile(
    r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}|\b\d{10}\b'
)
URL_REGEX = re.compile(
    r'https?://\S+|www\.\S+|(?:github|linkedin|gitlab|portfolio)\.com/\S+',
    re.IGNORECASE
)
ID_REGEX = re.compile(
    r'\b(?:roll|enrollment|student\s*id|reg(?:istration)?)\s*(?:no\.?|num(?:ber)?|#)?\s*[:\-]?\s*([A-Za-z0-9\-_]+)',
    re.IGNORECASE
)
NON_ALPHANUM_REGEX = re.compile(r'[^a-z0-9\s]')
WHITESPACE_REGEX = re.compile(r'\s+')
BULLET_START_REGEX = re.compile(r'^\s*[•·*\-–—\u2022\u25cf\u25cb\u25a0]\s*')

# Common English and resume words that appear in human names but should NOT
# be globally masked across resume bodies when matching single name tokens.
COMMON_NAME_EXCLUSIONS = {
    "will", "may", "mark", "art", "ray", "bill", "rob", "dean", "hope", "joy",
    "grace", "long", "young", "page", "major", "grant", "rose", "west", "north",
    "brown", "green", "white", "king", "lee", "bell", "day", "price", "field",
    "stone", "cross", "short", "smart", "rich", "fox", "wood", "ford", "best",
    "miles", "cole", "cook", "hall", "lane", "park", "post", "read", "rice",
    "ward", "bird", "camp", "case", "cash", "deal", "fast", "fish", "good",
    "hand", "hard", "hill", "hook", "horn", "hunt", "iron", "just", "kind",
    "lake", "land", "law", "like", "line", "lock", "lord", "love", "low",
    "main", "make", "many", "moon", "more", "most", "move", "much", "near",
    "need", "new", "next", "nice", "open", "over", "past", "peak", "peer",
    "plan", "play", "plus", "pool", "poor", "pure", "race", "rain", "rank",
    "real", "ring", "risk", "road", "rock", "root", "rule", "safe", "save",
    "seat", "seed", "self", "ship", "shop", "side", "sign", "site", "size",
    "skip", "slow", "snow", "soft", "sole", "song", "soon", "sort", "span",
    "spot", "star", "step", "stop", "sure", "take", "talk", "task", "team",
    "term", "test", "text", "time", "tree", "true", "turn", "type", "unit",
    "user", "view", "wait", "walk", "wall", "warm", "wash", "wave", "week",
    "well", "wide", "wild", "wind", "wire", "wise", "wish", "word", "work",
    "yard", "year", "zone", "and", "the", "for", "with", "from", "into"
}

STANDARD_ROLE_WORDS = {
    "engineer", "developer", "scientist", "analyst", "intern", "manager",
    "specialist", "consultant", "architect", "designer", "researcher", "lead",
    "student", "candidate", "associate", "programmer", "administrator", "officer"
}

STANDARD_ACADEMIC_WORDS = {
    "bachelor", "master", "phd", "btech", "mtech", "bba", "mba", "bs", "ms",
    "ba", "ma", "cgpa", "gpa", "diploma", "degree", "honors", "university",
    "college", "institute", "school"
}

STANDARD_HEADERS = {
    "education", "skills", "technical skills", "projects", "work experience",
    "experience", "summary", "professional summary", "certifications",
    "achievements", "interests", "activities", "contact", "profile", "links",
    "objective", "awards", "publications"
}


def mask_personal_identifiers(
    text: str,
    known_names: Optional[List[str]] = None,
) -> str:
    """
    Mask personal identifiable information (PII) including name, emails,
    phone numbers, student roll IDs, and web handles/URLs. This ensures similarity
    is computed on actual achievements, projects, skills, and experience rather than names.
    """
    if not text:
        return ""

    processed = text

    # 1. Mask URLs / Handles
    processed = URL_REGEX.sub(" [LINK] ", processed)

    # 2. Mask Emails
    processed = EMAIL_REGEX.sub(" [EMAIL] ", processed)

    # 3. Mask Phone Numbers
    processed = PHONE_REGEX.sub(" [PHONE] ", processed)

    # 4. Mask Student IDs / Roll Numbers
    processed = ID_REGEX.sub(" [ID] ", processed)

    # 5. Mask specific candidate names if supplied
    if known_names:
        for name in known_names:
            if not name or len(name.strip()) < 2:
                continue
            name_clean = name.strip()
            # Full name match is always safe
            pattern = re.compile(re.escape(name_clean), re.IGNORECASE)
            processed = pattern.sub(" [NAME] ", processed)
            # Mask individual first/last name parts only if length >= 3 and not common word
            for part in name_clean.split():
                if len(part) >= 3 and part.lower() not in COMMON_NAME_EXCLUSIONS:
                    p = re.compile(r'\b' + re.escape(part) + r'\b', re.IGNORECASE)
                    processed = p.sub(" [NAME] ", processed)

    # 6. Header candidate name heuristic:
    # If the candidate name wasn't in known_names, extract it from the resume header.
    # Check top lines before standard sections start.
    lines = processed.splitlines()
    name_already_masked = "[NAME]" in processed[:250]

    if not name_already_masked and lines:
        for i in range(min(5, len(lines))):
            raw_l = lines[i].strip()
            if not raw_l:
                continue

            # If line contains contact tokens, candidate name is often the prefix
            if any(token in raw_l for token in ["[EMAIL]", "[PHONE]", "[LINK]", "[ID]"]):
                prefix = re.split(r'\[EMAIL\]|\[PHONE\]|\[LINK\]|\[ID\]|[|•,]', raw_l)[0].strip()
                words = prefix.split()
                if 1 <= len(words) <= 4 and re.fullmatch(r'[A-Za-z\s.\'-]+', prefix):
                    lower_words = {w.lower() for w in words}
                    if (
                        not (lower_words & STANDARD_HEADERS)
                        and not (lower_words & STANDARD_ROLE_WORDS)
                        and not (lower_words & STANDARD_ACADEMIC_WORDS)
                    ):
                        replacement = " ".join(["[NAME]"] * len(words))
                        lines[i] = lines[i].replace(prefix, replacement, 1)
                        break
            else:
                # Standalone line
                words = raw_l.split()
                if 1 <= len(words) <= 4 and re.fullmatch(r'[A-Za-z\s.\'-]+', raw_l):
                    lower_words = {w.lower() for w in words}
                    if (
                        not (lower_words & STANDARD_HEADERS)
                        and not (lower_words & STANDARD_ROLE_WORDS)
                        and not (lower_words & STANDARD_ACADEMIC_WORDS)
                    ):
                        lines[i] = " ".join(["[NAME]"] * len(words))
                        break

        processed = "\n".join(lines)

    return processed


def normalize_text(text: str, known_names: Optional[List[str]] = None) -> str:
    """
    Produce canonical lowercased alphanumeric text with personal identifiers masked.
    """
    masked = mask_personal_identifiers(text, known_names)
    lowered = masked.lower()
    cleaned = NON_ALPHANUM_REGEX.sub(" ", lowered)
    normalized = WHITESPACE_REGEX.sub(" ", cleaned).strip()
    return normalized


def extract_substantive_bullets(text: str, min_length: int = MIN_SUBSTANTIVE_BULLET_LEN) -> List[str]:
    """
    Extract meaningful bullet points / project descriptions from resume text.
    Handles wrapped continuation lines common in PDF extraction and filters out
    section headings, short phrases, dates, and noise.
    """
    if not text:
        return []

    raw_lines = text.splitlines()
    reconstructed: List[str] = []
    current_bullet: str = ""

    # Reconstruct wrapped continuation lines
    for raw_line in raw_lines:
        stripped = raw_line.strip()
        if not stripped:
            if current_bullet:
                reconstructed.append(current_bullet)
                current_bullet = ""
            continue

        if BULLET_START_REGEX.match(raw_line):
            if current_bullet:
                reconstructed.append(current_bullet)
            current_bullet = BULLET_START_REGEX.sub("", raw_line).strip()
        else:
            if current_bullet:
                # Check if this line looks like a new section header
                if stripped.lower() in STANDARD_HEADERS:
                    reconstructed.append(current_bullet)
                    current_bullet = ""
                    reconstructed.append(stripped)
                else:
                    current_bullet += " " + stripped
            else:
                reconstructed.append(stripped)

    if current_bullet:
        reconstructed.append(current_bullet)

    substantive = []
    for line in reconstructed:
        cleaned_lower = line.lower()

        # Filter out short lines or section headers
        if len(line) < min_length:
            continue
        if cleaned_lower in STANDARD_HEADERS:
            continue
        # Filter out pure dates/years (e.g. "January 2021 - May 2024")
        if re.fullmatch(r'[\w\s,–\-/0-9]+', line) and len(line.split()) <= 4:
            if any(month in cleaned_lower for month in [
                "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "present"
            ]):
                continue

        # Normalize the bullet for comparison
        norm_bullet = WHITESPACE_REGEX.sub(" ", NON_ALPHANUM_REGEX.sub(" ", cleaned_lower)).strip()
        if len(norm_bullet) >= min_length:
            substantive.append(norm_bullet)

    return substantive


# ---------------------------------------------------------------------------
# Mathematical Similarity Algorithms
# ---------------------------------------------------------------------------

def compute_ngram_shingles(words: List[str], n: int = NGRAM_SIZE) -> Set[Tuple[str, ...]]:
    """Generate n-gram shingles from a list of words."""
    if len(words) < n:
        return set()
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def compute_jaccard_similarity(set_a: Set, set_b: Set) -> float:
    """Calculate Jaccard index between two sets."""
    if not set_a and not set_b:
        return 0.0
    union_len = len(set_a | set_b)
    if union_len == 0:
        return 0.0
    return len(set_a & set_b) / union_len


def compute_sequence_similarity(text_a: str, text_b: str) -> float:
    """
    Calculate sequence similarity ratio using Ratcliff-Obershelp (difflib).
    Returns value between 0.0 and 1.0.
    """
    if not text_a or not text_b:
        return 0.0
    matcher = difflib.SequenceMatcher(None, text_a, text_b)
    if matcher.quick_ratio() < 0.25:
        return matcher.quick_ratio()
    return matcher.ratio()


def compute_bullet_overlap(
    bullets_new: List[str],
    bullets_existing: List[str],
    similarity_cutoff: float = 0.82
) -> Tuple[float, List[str]]:
    """
    Check the proportion of substantive project/experience bullets from the new
    resume that match existing bullets.
    Returns (overlap_ratio, list_of_matching_snippets).
    """
    if not bullets_new or not bullets_existing:
        return 0.0, []

    matched_count = 0
    matching_snippets = []

    for nb in bullets_new:
        best_ratio = 0.0
        best_match = ""
        for eb in bullets_existing:
            if nb == eb:
                best_ratio = 1.0
                best_match = eb
                break
            ratio = difflib.SequenceMatcher(None, nb, eb).quick_ratio()
            if ratio >= similarity_cutoff:
                full_ratio = difflib.SequenceMatcher(None, nb, eb).ratio()
                if full_ratio > best_ratio:
                    best_ratio = full_ratio
                    best_match = eb

        if best_ratio >= similarity_cutoff:
            matched_count += 1
            if len(matching_snippets) < 3:
                snippet = nb[:80] + "..." if len(nb) > 80 else nb
                matching_snippets.append(snippet)

    overlap_ratio = matched_count / len(bullets_new)
    return overlap_ratio, matching_snippets


# ---------------------------------------------------------------------------
# Core Pure-Comparison Logic
# ---------------------------------------------------------------------------

def compare_resume_texts(
    new_text: str,
    existing_text: str,
    new_student_name: Optional[str] = None,
    existing_student_name: Optional[str] = None,
    new_file_hash: Optional[str] = None,
    existing_file_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deterministic comparison between two resumes to detect plagiarism or clone
    with changed names.

    Ensemble logic:
    1. Exact file hash check (100% duplicate file)
    2. Name-masked normalized text comparison
    3. Word 3-gram Jaccard similarity (permutation-resistant)
    4. SequenceMatcher contiguous block ratio
    5. Substantive bullet / project description overlap
    """
    # 1. Exact file hash match
    if new_file_hash and existing_file_hash and new_file_hash == existing_file_hash:
        return {
            "similarity_score": 1.0,
            "is_duplicate": True,
            "confidence": "high",
            "metrics": {
                "file_hash_match": 1.0,
                "ngram_jaccard": 1.0,
                "sequence_ratio": 1.0,
                "bullet_overlap": 1.0,
            },
            "reasons": ["Exact binary file hash match with an existing resume."],
            "matching_snippets": ["Exact identical file."],
        }

    # Normalize texts with names masked
    names_to_mask = []
    if new_student_name:
        names_to_mask.append(new_student_name)
    if existing_student_name:
        names_to_mask.append(existing_student_name)

    norm_new = normalize_text(new_text, names_to_mask)
    norm_existing = normalize_text(existing_text, names_to_mask)

    if not norm_new or not norm_existing:
        return {
            "similarity_score": 0.0,
            "is_duplicate": False,
            "confidence": "none",
            "metrics": {"ngram_jaccard": 0.0, "sequence_ratio": 0.0, "bullet_overlap": 0.0},
            "reasons": [],
            "matching_snippets": [],
        }

    words_new = norm_new.split()
    words_existing = norm_existing.split()

    # Guard: Require substantive word length to avoid false positives on 1-word or minimal texts
    if len(words_new) < MIN_TEXT_WORDS_FOR_COMPARISON or len(words_existing) < MIN_TEXT_WORDS_FOR_COMPARISON:
        return {
            "similarity_score": 0.0,
            "is_duplicate": False,
            "confidence": "none",
            "metrics": {"ngram_jaccard": 0.0, "sequence_ratio": 0.0, "bullet_overlap": 0.0},
            "reasons": ["Insufficient text content (< 15 words) for structural plagiarism verification."],
            "matching_snippets": [],
        }

    # Exact normalized text match (identical resume minus personal names/contacts)
    if norm_new == norm_existing:
        return {
            "similarity_score": 1.0,
            "is_duplicate": True,
            "confidence": "high",
            "metrics": {
                "file_hash_match": 0.0,
                "ngram_jaccard": 1.0,
                "sequence_ratio": 1.0,
                "bullet_overlap": 1.0,
            },
            "reasons": ["100% identical body content after masking personal applicant details."],
            "matching_snippets": ["All projects, experience, and coursework descriptions match perfectly."],
        }

    # Metric A: Word N-gram Jaccard
    shingles_new = compute_ngram_shingles(words_new, n=NGRAM_SIZE)
    shingles_existing = compute_ngram_shingles(words_existing, n=NGRAM_SIZE)
    ngram_jaccard = compute_jaccard_similarity(shingles_new, shingles_existing)

    # Metric B: Sequence ratio
    sequence_ratio = compute_sequence_similarity(norm_new, norm_existing)

    # Metric C: Bullet overlap
    bullets_new = extract_substantive_bullets(new_text)
    bullets_existing = extract_substantive_bullets(existing_text)
    bullet_overlap, matching_snippets = compute_bullet_overlap(bullets_new, bullets_existing)

    # Composite Ensemble Calculation:
    # If neither resume has extracted bullets (e.g. paragraph-based resumes), rebalance
    # weights between sequence ratio and n-gram shingling so bullet absence doesn't depress score.
    if bullets_new and bullets_existing:
        weighted_score = (sequence_ratio * 0.45) + (ngram_jaccard * 0.35) + (bullet_overlap * 0.20)
        composite_similarity = round(max(weighted_score, ngram_jaccard * 0.95, bullet_overlap * 0.90), 4)
    else:
        weighted_score = (sequence_ratio * 0.55) + (ngram_jaccard * 0.45)
        composite_similarity = round(max(weighted_score, ngram_jaccard * 0.95), 4)

    is_duplicate = composite_similarity >= DUPLICATE_SIMILARITY_THRESHOLD
    is_suspicious = (not is_duplicate) and (composite_similarity >= SUSPICIOUS_SIMILARITY_THRESHOLD)

    confidence = "none"
    reasons = []

    if is_duplicate:
        confidence = "high"
        reasons.append(
            f"High resume similarity ({composite_similarity * 100:.1f}%) detected exceeding {DUPLICATE_SIMILARITY_THRESHOLD * 100:.0f}% threshold."
        )
        if sequence_ratio >= 0.70:
            reasons.append(f"Text sequence alignment: {sequence_ratio * 100:.1f}% common sequence ratio.")
        if ngram_jaccard >= 0.65:
            reasons.append(f"Word n-gram shingle overlap: {ngram_jaccard * 100:.1f}%.")
        if bullet_overlap >= 0.65:
            reasons.append(f"Substantive project/experience bullet overlap: {bullet_overlap * 100:.1f}%.")
    elif is_suspicious:
        confidence = "medium"
        reasons.append(
            f"Suspicious similarity ({composite_similarity * 100:.1f}%) detected with an existing resume. Flagged for review."
        )

    return {
        "similarity_score": composite_similarity,
        "is_duplicate": is_duplicate,
        "confidence": confidence,
        "metrics": {
            "file_hash_match": 0.0,
            "ngram_jaccard": round(ngram_jaccard, 4),
            "sequence_ratio": round(sequence_ratio, 4),
            "bullet_overlap": round(bullet_overlap, 4),
        },
        "reasons": reasons,
        "matching_snippets": matching_snippets,
    }


# ---------------------------------------------------------------------------
# Database-Integrated Verification Function
# ---------------------------------------------------------------------------

async def verify_resume_uniqueness(
    db: AsyncSession,
    current_student_id: uuid.UUID,
    raw_text: str,
    file_hash: Optional[str] = None,
    current_student_name: Optional[str] = None,
    current_resume_id: Optional[uuid.UUID] = None,
) -> ResumeVerificationResult:
    """
    Verifies an uploaded resume against all previously uploaded resumes from
    OTHER students in the database.

    Guarantees:
    - Never flags a student for re-uploading or updating their own resume.
    - Excludes previously rejected duplicate resumes so fraudulent uploads don't become reference resumes.
    - Catches direct file clones via file_hash.
    - Catches resumes copied with only name/header changes via multi-metric text similarity.
    - Uses fast mathematical pre-filtering for scalable querying across large databases.
    """
    # 1. Fetch resumes belonging to OTHER students that were NOT rejected duplicates
    # Use outerjoin to safely handle records without dropping test fixtures or loose rows
    query = (
        select(Resume, User.full_name)
        .outerjoin(Student, Resume.student_id == Student.id)
        .outerjoin(User, Student.user_id == User.id)
        .where(Resume.student_id != current_student_id)
        .where(Resume.status != "rejected_duplicate")
    )

    if current_resume_id:
        query = query.where(Resume.id != current_resume_id)

    result = await db.execute(query)
    candidate_records = result.all()

    if not candidate_records:
        return ResumeVerificationResult(
            is_duplicate=False,
            confidence="none",
            similarity_score=0.0,
            reasons=["No previous resumes from other students in the database to compare against."],
            status="verified",
        )

    # 2. Check for exact file hash match first (Tier 1 quick exit)
    if file_hash:
        for existing_resume, existing_student_name in candidate_records:
            if existing_resume.file_hash and existing_resume.file_hash == file_hash:
                logger.warning(
                    f"[ResumeValidator] Exact file_hash match! Student {current_student_id} "
                    f"uploaded identical file previously uploaded by student {existing_resume.student_id}"
                )
                return ResumeVerificationResult(
                    is_duplicate=True,
                    confidence="high",
                    similarity_score=1.0,
                    matched_resume_id=existing_resume.id,
                    matched_student_id=existing_resume.student_id,
                    matched_student_name=existing_student_name,
                    matched_file_name=existing_resume.file_name,
                    metrics={
                        "file_hash_match": 1.0,
                        "ngram_jaccard": 1.0,
                        "sequence_ratio": 1.0,
                        "bullet_overlap": 1.0,
                    },
                    reasons=[
                        f"Exact duplicate file: SHA-256 hash matches resume previously uploaded by {existing_student_name or 'another student'}."
                    ],
                    matching_snippets=["Entire file is an exact binary duplicate."],
                    status="flagged_duplicate",
                )

    # 3. Check text similarity against other students' resumes (Tier 2-5)
    highest_similarity = 0.0
    best_match_result: Optional[Dict[str, Any]] = None
    best_matched_resume: Optional[Resume] = None
    best_matched_name: Optional[str] = None

    norm_new_words = normalize_text(raw_text, [current_student_name] if current_student_name else None).split()
    len_new_words = len(norm_new_words)
    set_new_words = set(norm_new_words)

    for existing_resume, existing_student_name in candidate_records:
        existing_text = existing_resume.raw_text

        # Backfill raw_text from file if empty but file exists
        if not existing_text and existing_resume.file_path and os.path.exists(existing_resume.file_path):
            try:
                existing_text = extract_text_from_file(existing_resume.file_path, existing_resume.mime_type)
                existing_resume.raw_text = existing_text
                db.add(existing_resume)
            except Exception as e:
                logger.debug(f"[ResumeValidator] Could not read existing resume file: {e}")
                existing_text = ""

        if not existing_text:
            continue

        # Fast mathematical pre-filters to avoid quadratic SequenceMatcher on unrelated resumes
        if len_new_words >= MIN_TEXT_WORDS_FOR_COMPARISON:
            norm_ex_words = normalize_text(existing_text, [existing_student_name] if existing_student_name else None).split()
            len_ex_words = len(norm_ex_words)

            if len_ex_words >= MIN_TEXT_WORDS_FOR_COMPARISON:
                # Filter A: Length ratio bound
                min_len = min(len_new_words, len_ex_words)
                max_len = max(len_new_words, len_ex_words)
                if (min_len / max_len) < 0.35:
                    continue

                # Filter B: Word token vocabulary overlap
                set_ex_words = set(norm_ex_words)
                token_jaccard = len(set_new_words & set_ex_words) / len(set_new_words | set_ex_words)
                if token_jaccard < 0.25:
                    continue

        comp = compare_resume_texts(
            new_text=raw_text,
            existing_text=existing_text,
            new_student_name=current_student_name,
            existing_student_name=existing_student_name,
            new_file_hash=file_hash,
            existing_file_hash=existing_resume.file_hash,
        )

        sim = comp["similarity_score"]
        if sim > highest_similarity:
            highest_similarity = sim
            best_match_result = comp
            best_matched_resume = existing_resume
            best_matched_name = existing_student_name

    if best_match_result and best_matched_resume and highest_similarity >= DUPLICATE_SIMILARITY_THRESHOLD:
        logger.warning(
            f"[ResumeValidator] Duplicate detected! Similarity: {highest_similarity * 100:.1f}% "
            f"between student {current_student_id} and existing resume {best_matched_resume.id} "
            f"from student {best_matched_resume.student_id} ({best_matched_name})"
        )
        return ResumeVerificationResult(
            is_duplicate=True,
            confidence="high",
            similarity_score=highest_similarity,
            matched_resume_id=best_matched_resume.id,
            matched_student_id=best_matched_resume.student_id,
            matched_student_name=best_matched_name,
            matched_file_name=best_matched_resume.file_name,
            metrics=best_match_result["metrics"],
            reasons=best_match_result["reasons"],
            matching_snippets=best_match_result["matching_snippets"],
            status="flagged_duplicate",
        )

    if best_match_result and best_matched_resume and highest_similarity >= SUSPICIOUS_SIMILARITY_THRESHOLD:
        return ResumeVerificationResult(
            is_duplicate=False,
            confidence="medium",
            similarity_score=highest_similarity,
            matched_resume_id=best_matched_resume.id,
            matched_student_id=best_matched_resume.student_id,
            matched_student_name=best_matched_name,
            matched_file_name=best_matched_resume.file_name,
            metrics=best_match_result["metrics"],
            reasons=best_match_result["reasons"],
            matching_snippets=best_match_result["matching_snippets"],
            status="suspicious",
        )

    return ResumeVerificationResult(
        is_duplicate=False,
        confidence="none",
        similarity_score=highest_similarity,
        metrics=best_match_result["metrics"] if best_match_result else {},
        reasons=["Resume passed uniqueness verification."],
        status="verified",
    )
