"""
Governed connectors for coding-platform data (GitHub REST API, LeetCode GraphQL).

Rules enforced here, not in the agents:
- source-specific consent (`github`, `leetcode`) must be `granted` for the
  exact handle on the student's profile before any network call or cache read;
- handles are validated before use;
- failures are reported with an explicit status — never replaced by fixtures;
- normalised results are cached in `coding_analytics` with retrieval time so
  the report can show source, retrieval time and freshness.
"""
import json
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import httpx
from sqlalchemy import select

from app.config import settings
from app.connectors.base import BaseConnector
from app.connectors.student_connector import StudentConnector
from app.models.analysis import CodingAnalytics

STATUS_OK = "ok"
STATUS_NOT_CONSENTED = "not_consented"
STATUS_NOT_CONFIGURED = "not_configured"
STATUS_INVALID_HANDLE = "invalid_handle"
STATUS_NOT_FOUND = "not_found"
STATUS_RATE_LIMITED = "rate_limited"
STATUS_UNAVAILABLE = "unavailable"

GITHUB_HANDLE_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
LEETCODE_HANDLE_RE = re.compile(r"^[A-Za-z0-9_-]{1,30}$")

PLATFORMS = ("github", "leetcode")


def validate_handle(platform: str, handle: Optional[str]) -> bool:
    if not handle:
        return False
    if platform == "github":
        return bool(GITHUB_HANDLE_RE.match(handle))
    if platform == "leetcode":
        return bool(LEETCODE_HANDLE_RE.match(handle))
    return False


# ---------------------------------------------------------------------------
# Normalisers (pure functions — unit-tested with recorded API payloads)
# ---------------------------------------------------------------------------

def normalize_github(user: Dict[str, Any], repos: list, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    original = [r for r in repos if not r.get("fork")]
    languages = Counter(r.get("language") for r in original if r.get("language"))
    recent_cutoff = now - timedelta(days=90)

    def _ts(v: Optional[str]) -> Optional[datetime]:
        if not v:
            return None
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return None

    pushed = [_ts(r.get("pushed_at")) for r in original]
    pushed = [p for p in pushed if p]
    monthly = Counter(p.strftime("%Y-%m") for p in pushed if p >= now - timedelta(days=365))
    top = sorted(original, key=lambda r: (r.get("stargazers_count", 0), r.get("pushed_at") or ""), reverse=True)[:6]
    return {
        "username": user.get("login"),
        "profile_url": user.get("html_url"),
        "public_repos": user.get("public_repos", 0),
        "followers": user.get("followers", 0),
        "account_created_at": user.get("created_at"),
        "repos_analyzed": len(repos),
        "original_repos": len(original),
        "languages": dict(languages.most_common()),
        "recently_active_repos": sum(1 for p in pushed if p >= recent_cutoff),
        "last_push_at": max(pushed).isoformat() if pushed else None,
        "repo_activity_by_month": [{"month": m, "repos_pushed": c} for m, c in sorted(monthly.items())],
        "top_repositories": [
            {
                "name": r.get("name"),
                "language": r.get("language"),
                "stars": r.get("stargazers_count", 0),
                "description": (r.get("description") or "")[:200],
                "topics": r.get("topics", [])[:8],
                "pushed_at": r.get("pushed_at"),
                "url": r.get("html_url"),
            }
            for r in top
        ],
    }


def normalize_leetcode(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = payload.get("data") or {}
    user = data.get("matchedUser") or {}
    contest = data.get("userContestRanking") or {}

    difficulty = {"easy": 0, "medium": 0, "hard": 0}
    total = 0
    for row in ((user.get("submitStatsGlobal") or {}).get("acSubmissionNum") or []):
        d = (row.get("difficulty") or "").lower()
        if d == "all":
            total = int(row.get("count") or 0)
        elif d in difficulty:
            difficulty[d] = int(row.get("count") or 0)
    if not total:
        total = sum(difficulty.values())

    topics = []
    tags = user.get("tagProblemCounts") or {}
    for level in ("advanced", "intermediate", "fundamental"):
        for t in tags.get(level) or []:
            topics.append({"topic": t.get("tagName"), "solved": int(t.get("problemsSolved") or 0), "tier": level})
    topics.sort(key=lambda t: t["solved"], reverse=True)

    calendar = user.get("userCalendar") or {}
    monthly: Dict[str, int] = defaultdict(int)
    raw_cal = calendar.get("submissionCalendar")
    if raw_cal:
        try:
            for ts, count in json.loads(raw_cal).items():
                month = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m")
                monthly[month] += int(count)
        except (ValueError, TypeError):
            pass

    languages = {
        l.get("languageName"): int(l.get("problemsSolved") or 0)
        for l in (user.get("languageProblemCount") or []) if l.get("languageName")
    }

    return {
        "username": user.get("username"),
        "profile_url": f"https://leetcode.com/u/{user.get('username')}/" if user.get("username") else None,
        "total_solved": total,
        "difficulty_distribution": difficulty,
        "ranking": (user.get("profile") or {}).get("ranking"),
        "contest": {
            "attended": contest.get("attendedContestsCount") or 0,
            "rating": round(contest["rating"]) if contest.get("rating") else None,
            "global_ranking": contest.get("globalRanking"),
            "top_percentage": contest.get("topPercentage"),
        },
        "topics": topics,
        "monthly_activity": [{"month": m, "submissions": c} for m, c in sorted(monthly.items())][-12:],
        "streak_days": calendar.get("streak") or 0,
        "active_days": calendar.get("totalActiveDays") or 0,
        "languages": languages,
    }


LEETCODE_QUERY = """
query userProfile($username: String!) {
  matchedUser(username: $username) {
    username
    profile { ranking }
    submitStatsGlobal { acSubmissionNum { difficulty count } }
    tagProblemCounts {
      advanced { tagName problemsSolved }
      intermediate { tagName problemsSolved }
      fundamental { tagName problemsSolved }
    }
    userCalendar { streak totalActiveDays submissionCalendar }
    languageProblemCount { languageName problemsSolved }
  }
  userContestRanking(username: $username) {
    attendedContestsCount rating globalRanking topPercentage
  }
}
"""


# ---------------------------------------------------------------------------
# Live API clients
# ---------------------------------------------------------------------------

class GitHubClient:
    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.transport = transport

    async def fetch(self, handle: str) -> Tuple[str, Optional[Dict[str, Any]], Optional[str]]:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "placement-readiness-portal"}
        if settings.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
        base = settings.GITHUB_API_URL.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=settings.CONNECTOR_TIMEOUT_SECONDS, headers=headers,
                                         transport=self.transport) as client:
                resp = await client.get(f"{base}/users/{handle}")
                if resp.status_code == 404:
                    return STATUS_NOT_FOUND, None, f"GitHub user '{handle}' does not exist"
                if resp.status_code in (403, 429) and resp.headers.get("x-ratelimit-remaining") == "0":
                    return STATUS_RATE_LIMITED, None, "GitHub API rate limit reached; set GITHUB_TOKEN or retry later"
                if resp.status_code != 200:
                    return STATUS_UNAVAILABLE, None, f"GitHub API returned HTTP {resp.status_code}"
                user = resp.json()
                repos_resp = await client.get(
                    f"{base}/users/{handle}/repos", params={"per_page": 100, "sort": "pushed", "type": "owner"}
                )
                if repos_resp.status_code != 200:
                    return STATUS_UNAVAILABLE, None, f"GitHub repositories request returned HTTP {repos_resp.status_code}"
                repos = repos_resp.json()
                if not isinstance(user, dict) or not isinstance(repos, list):
                    return STATUS_UNAVAILABLE, None, "Unexpected GitHub response format"
        except httpx.TimeoutException:
            return STATUS_UNAVAILABLE, None, "GitHub API timed out"
        except (httpx.HTTPError, ValueError) as exc:
            return STATUS_UNAVAILABLE, None, f"GitHub API error: {exc.__class__.__name__}"
        return STATUS_OK, normalize_github(user, repos), None


class LeetCodeClient:
    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.transport = transport

    async def fetch(self, handle: str) -> Tuple[str, Optional[Dict[str, Any]], Optional[str]]:
        headers = {
            "Content-Type": "application/json",
            "Referer": "https://leetcode.com/",
            "User-Agent": "placement-readiness-portal",
        }
        try:
            async with httpx.AsyncClient(timeout=settings.CONNECTOR_TIMEOUT_SECONDS, headers=headers,
                                         transport=self.transport) as client:
                resp = await client.post(
                    settings.LEETCODE_GRAPHQL_URL,
                    json={"query": LEETCODE_QUERY, "variables": {"username": handle}},
                )
                if resp.status_code == 429:
                    return STATUS_RATE_LIMITED, None, "LeetCode rate limit reached; retry later"
                if resp.status_code != 200:
                    return STATUS_UNAVAILABLE, None, f"LeetCode returned HTTP {resp.status_code}"
                payload = resp.json()
        except httpx.TimeoutException:
            return STATUS_UNAVAILABLE, None, "LeetCode timed out"
        except (httpx.HTTPError, ValueError) as exc:
            return STATUS_UNAVAILABLE, None, f"LeetCode error: {exc.__class__.__name__}"

        if not isinstance(payload, dict):
            return STATUS_UNAVAILABLE, None, "Unexpected LeetCode response format"
        data = payload.get("data") or {}
        if not data.get("matchedUser"):
            errors = " ".join(str(e.get("message", "")) for e in payload.get("errors") or [])
            if "not exist" in errors.lower() or data.get("matchedUser") is None:
                return STATUS_NOT_FOUND, None, f"LeetCode user '{handle}' was not found"
            return STATUS_UNAVAILABLE, None, "LeetCode returned no profile data"
        return STATUS_OK, normalize_leetcode(payload), None


class CodingConnector(BaseConnector):
    """
    Consent-gated access to one student's coding-platform data.
    Returns {source, status, data, retrieved_at, from_cache, source_url, error};
    when a source is unavailable `data` is None — nothing is substituted.
    """

    def __init__(self, db, actor_id: str = "system"):
        super().__init__(db, actor_id)
        self.clients = {"github": GitHubClient(), "leetcode": LeetCodeClient()}

    async def get_platform_data(self, student_id: uuid.UUID, platform: str, handle: Optional[str]) -> Dict[str, Any]:
        result: Dict[str, Any] = {"source": platform, "handle": handle, "data": None, "from_cache": False,
                                  "source_url": None, "error": None, "retrieved_at": None}
        consents = await StudentConnector(self.db, self.actor_id).get_consent_status(student_id)
        if consents.get(platform, {}).get("status") != "granted":
            return {**result, "status": STATUS_NOT_CONSENTED, "error": "Consent for this source was not granted"}
        if not handle:
            return {**result, "status": STATUS_NOT_CONFIGURED, "error": "No handle provided"}
        if not validate_handle(platform, handle):
            return {**result, "status": STATUS_INVALID_HANDLE, "error": f"'{handle}' is not a valid {platform} handle"}

        row = (await self.safe_execute(select(CodingAnalytics).where(
            CodingAnalytics.student_id == student_id, CodingAnalytics.platform == platform))).scalars().first()
        fresh = datetime.now(timezone.utc) - timedelta(hours=settings.CODING_DATA_STALE_HOURS)
        if (row is not None and row.fetch_status == STATUS_OK and (row.handle or "").lower() == handle.lower()
                and row.last_synced_at and row.last_synced_at >= fresh and row.profile_data):
            return {**result, "status": STATUS_OK, "data": row.profile_data, "from_cache": True,
                    "source_url": row.source_url, "retrieved_at": row.last_synced_at.isoformat()}

        status_, data, error = await self.clients[platform].fetch(handle)
        now = datetime.now(timezone.utc)
        if row is None:
            row = CodingAnalytics(student_id=student_id, platform=platform)
            self.db.add(row)
        row.handle, row.fetch_status, row.error_message = handle, status_, error
        if status_ == STATUS_OK and data:
            row.profile_data = data
            row.source_url = data.get("profile_url")
            row.last_synced_at = now
            if platform == "leetcode":
                dist = data.get("difficulty_distribution", {})
                row.total_solved = data.get("total_solved", 0)
                row.easy_solved, row.medium_solved, row.hard_solved = dist.get("easy", 0), dist.get("medium", 0), dist.get("hard", 0)
                row.contest_rating = (data.get("contest") or {}).get("rating")
                row.contests_participated = (data.get("contest") or {}).get("attended", 0)
                row.streak_days = data.get("streak_days", 0)
                row.active_days = data.get("active_days", 0)
                row.topic_stats = data.get("topics")
        await self.db.commit()
        if status_ == STATUS_OK:
            return {**result, "status": STATUS_OK, "data": data, "source_url": data.get("profile_url"),
                    "retrieved_at": now.isoformat()}
        return {**result, "status": status_, "error": error}
