"""
Test support: isolated PostgreSQL schema per test, HTTP client, account helpers,
resume fixtures and recorded GitHub/LeetCode payloads.

Fixture data here is used only by automated tests and is never loaded by the app.
"""
import io
import json
import os
import uuid
from typing import Any, Dict, Optional, Tuple

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

STUDENT_PASSWORD = "Student-Passw0rd"
OFFICER_PASSWORD = "Officer-Passw0rd"


def _db_url() -> str:
    from app.config import settings
    return os.environ.get("TEST_DATABASE_URL") or settings.DATABASE_URL


@pytest.fixture
async def db_factory():
    """A fresh schema with all tables; app sessions and connectors are pointed at it."""
    from app import database
    from app.database import Base, get_db
    from app.main import app as fastapi_app
    import app.models as _models  # noqa: F401  (register all models)

    schema = f"test_{uuid.uuid4().hex[:12]}"
    url = _db_url()
    admin_engine = create_async_engine(url, poolclass=NullPool)
    async with admin_engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, poolclass=NullPool, connect_args={"server_settings": {"search_path": schema}})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    old_factory = database.async_session_factory
    database.async_session_factory = factory
    fastapi_app.dependency_overrides[get_db] = _get_db
    try:
        yield factory
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)
        database.async_session_factory = old_factory
        await engine.dispose()
        async with admin_engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin_engine.dispose()


@pytest.fixture
async def client(db_factory):
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def reference_data(db_factory):
    from app.services.reference_data import seed_reference_data
    async with db_factory() as db:
        return await seed_reference_data(db)


# ---------------------------------------------------------------------------
# Account helpers
# ---------------------------------------------------------------------------

def auth(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def register_student(client, email: Optional[str] = None, name: str = "Asha Rao") -> Dict[str, Any]:
    email = email or f"student-{uuid.uuid4().hex[:8]}@college.edu"
    r = await client.post("/api/v1/auth/register", json={"email": email, "password": STUDENT_PASSWORD, "full_name": name})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"email": email, "token": body["access_token"], "headers": auth(body["access_token"]),
            "user_id": body["user"]["id"]}


async def create_officer(client, db_factory, email: Optional[str] = None) -> Dict[str, Any]:
    """Placement Cell accounts are created server-side (scripts/create_user.py), then log in."""
    from app.services.auth import create_user
    email = email or f"tpo-{uuid.uuid4().hex[:8]}@college.edu"
    async with db_factory() as db:
        await create_user(db, email=email, password=OFFICER_PASSWORD, full_name="Dr. Meera Iyer", role="placement_officer")
        await db.commit()
    r = await client.post("/api/v1/auth/login", data={"username": email, "password": OFFICER_PASSWORD})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"email": email, "token": token, "headers": auth(token)}


async def grant(client, headers, *consent_types: str) -> None:
    for ct in consent_types:
        r = await client.post("/api/v1/consents/me/grant", json={"consent_type": ct}, headers=headers)
        assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Resume fixtures
# ---------------------------------------------------------------------------

SOFTWARE_RESUME = """Asha Rao
asha@college.edu | github.com/asha-dev

Summary
Final-year computer engineering student building backend services.

Technical Skills
Languages: Python, Java, SQL
Tools: Git, Docker, Linux

Projects
Campus Event API
- Built a REST API with Python, FastAPI and PostgreSQL for 2,000 students
- Containerised with Docker and deployed on Linux
Library Management System
- Java and SQL desktop application using object oriented design

Experience
Backend Intern - Acme Labs
- 2025 to 2025, wrote Python services and SQL reports

Education
B.Tech Computer Engineering, Pune Institute of Technology
CGPA: 8.4 / 10
"""

CORE_RESUME = """Rohan Kulkarni

Objective
Mechanical engineering student interested in product design.

Skills
AutoCAD, SolidWorks, MATLAB, Thermodynamics

Projects
Gearbox Design
- Designed a two-stage gearbox in SolidWorks and verified stresses in ANSYS
Solar Dryer
- Thermodynamics analysis of a solar crop dryer using MATLAB

Education
B.E. Mechanical Engineering, Government College of Engineering
CGPA 7.6
"""


def make_docx(text_: str) -> bytes:
    import docx
    d = docx.Document()
    for line in text_.split("\n"):
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def upload(client, headers, text_: str = SOFTWARE_RESUME, roles=("software_engineer",), **form):
    data = {"target_roles": json.dumps(list(roles)), **{k: str(v) for k, v in form.items()}}
    return await client.post("/api/v1/process/upload", headers=headers, data=data,
                             files={"file": ("resume.docx", make_docx(text_), DOCX_MIME)})


# ---------------------------------------------------------------------------
# Recorded coding-platform payloads (shape of the real APIs)
# ---------------------------------------------------------------------------

def github_payload(login: str = "asha-dev") -> Tuple[Dict[str, Any], list]:
    user = {"login": login, "html_url": f"https://github.com/{login}", "public_repos": 7, "followers": 12,
            "created_at": "2022-08-01T10:00:00Z"}
    repos = [
        {"name": "campus-event-api", "language": "Python", "fork": False, "stargazers_count": 5,
         "pushed_at": "2026-10-01T09:00:00Z", "description": "FastAPI service", "topics": ["fastapi"],
         "html_url": f"https://github.com/{login}/campus-event-api"},
        {"name": "dsa-practice", "language": "Python", "fork": False, "stargazers_count": 1,
         "pushed_at": "2026-09-20T09:00:00Z", "description": "", "topics": [], "html_url": "x"},
        {"name": "ml-notebooks", "language": "Jupyter Notebook", "fork": False, "stargazers_count": 0,
         "pushed_at": "2026-05-02T09:00:00Z", "description": "", "topics": [], "html_url": "x"},
        {"name": "library-system", "language": "Java", "fork": False, "stargazers_count": 2,
         "pushed_at": "2025-12-11T09:00:00Z", "description": "", "topics": [], "html_url": "x"},
        {"name": "dotfiles", "language": "Shell", "fork": False, "stargazers_count": 0,
         "pushed_at": "2025-01-11T09:00:00Z", "description": "", "topics": [], "html_url": "x"},
        {"name": "react-fork", "language": "JavaScript", "fork": True, "stargazers_count": 0,
         "pushed_at": "2024-01-11T09:00:00Z", "description": "", "topics": [], "html_url": "x"},
    ]
    return user, repos


def leetcode_payload(username: str = "asha_codes", total: int = 214) -> Dict[str, Any]:
    return {"data": {
        "matchedUser": {
            "username": username,
            "profile": {"ranking": 210345},
            "submitStatsGlobal": {"acSubmissionNum": [
                {"difficulty": "All", "count": total}, {"difficulty": "Easy", "count": 98},
                {"difficulty": "Medium", "count": 101}, {"difficulty": "Hard", "count": total - 199},
            ]},
            "tagProblemCounts": {
                "advanced": [{"tagName": "Dynamic Programming", "problemsSolved": 22}],
                "intermediate": [{"tagName": "Hash Table", "problemsSolved": 47}, {"tagName": "Tree", "problemsSolved": 25}],
                "fundamental": [{"tagName": "Array", "problemsSolved": 120}, {"tagName": "String", "problemsSolved": 61}],
            },
            "userCalendar": {"streak": 9, "totalActiveDays": 133,
                             "submissionCalendar": '{"1748736000": 6, "1751328000": 11, "1754006400": 15, "1756684800": 19, "1759276800": 24, "1760486400": 30}'},
            "languageProblemCount": [{"languageName": "Python3", "problemsSolved": 180}, {"languageName": "Java", "problemsSolved": 34}],
        },
        "userContestRanking": {"attendedContestsCount": 6, "rating": 1586.4, "globalRanking": 120334, "topPercentage": 31.2},
    }}


@pytest.fixture
def fake_platforms(monkeypatch):
    """
    Replace the live GitHub/LeetCode HTTP clients with recorded responses.
    Configure per handle: fake_platforms["github"]["asha-dev"] = ("ok", None) etc.
    """
    from app.connectors import coding_connector as cc

    registry = {"github": {}, "leetcode": {}, "calls": []}

    async def gh_fetch(self, handle):
        registry["calls"].append(("github", handle))
        status, err = registry["github"].get(handle, ("not_found", f"GitHub user '{handle}' does not exist"))
        if status != "ok":
            return status, None, err
        user, repos = github_payload(handle)
        return "ok", cc.normalize_github(user, repos), None

    async def lc_fetch(self, handle):
        registry["calls"].append(("leetcode", handle))
        status, err = registry["leetcode"].get(handle, ("not_found", f"LeetCode user '{handle}' was not found"))
        if status != "ok":
            return status, None, err
        total = registry.get("leetcode_totals", {}).get(handle, 214)
        return "ok", cc.normalize_leetcode(leetcode_payload(handle, total)), None

    monkeypatch.setattr(cc.GitHubClient, "fetch", gh_fetch)
    monkeypatch.setattr(cc.LeetCodeClient, "fetch", lc_fetch)
    return registry


__all__ = [
    "db_factory", "client", "reference_data", "fake_platforms",
    "auth", "register_student", "create_officer", "grant",
    "upload", "make_docx", "SOFTWARE_RESUME", "CORE_RESUME", "DOCX_MIME",
    "github_payload", "leetcode_payload", "STUDENT_PASSWORD", "OFFICER_PASSWORD",
]
