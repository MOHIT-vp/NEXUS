"""Mock interview: timed sessions, grading per section, one submission per session, students only."""
import time

import pytest

from app.core.mock_bank import CODING, SECTIONS
from app.services import mock_interview as svc
from tests.support import create_officer, register_student

REFERENCE = {
    "mock-reverse-words": "def reverse_words(s):\n    return ' '.join(reversed(s.split()))\n",
    "mock-max-subarray": "def max_subarray(nums):\n    best = cur = nums[0]\n    for x in nums[1:]:\n        cur = max(x, cur + x)\n        best = max(best, cur)\n    return best\n",
    "mock-first-unique": "def first_unique_char(s):\n    for i, c in enumerate(s):\n        if s.count(c) == 1:\n            return i\n    return -1\n",
    "mock-anagram": "def is_anagram(s, t):\n    return sorted(s) == sorted(t)\n",
    "mock-missing-number": "def missing_number(nums):\n    n = len(nums)\n    return n * (n + 1) // 2 - sum(nums)\n",
}


def test_bank_is_well_formed():
    ids = [q["id"] for m in SECTIONS.values() for q in m["bank"]]
    assert len(ids) == len(set(ids))
    for key, m in SECTIONS.items():
        if m["kind"] == "mcq":
            for q in m["bank"]:
                assert len(q["options"]) == 4 and 0 <= q["answer"] < 4 and q["explanation"]
    assert {q["topic"] for q in SECTIONS["cs_fundamentals"]["bank"]} == {"DBMS", "OS", "CN", "OOPs"}


@pytest.mark.parametrize("problem", CODING, ids=[p["id"] for p in CODING])
def test_coding_problems_accept_a_correct_solution(problem):
    from app.api.v1.coding import run_code_execution
    res = run_code_execution(problem, REFERENCE[problem["id"]], mode="submit")
    assert res["all_passed"], res


def test_session_hides_answers_and_grades_mcq():
    s = svc.start_session("u1", "cs_fundamentals", 4, 10, subjects=["DBMS"])
    assert len(s["questions"]) == 4 and all("answer" not in q and "explanation" not in q for q in s["questions"])
    by_id = {q["id"]: q for q in SECTIONS["cs_fundamentals"]["bank"]}
    assert all(by_id[q["id"]]["topic"] == "DBMS" for q in s["questions"])
    answers = {q["id"]: by_id[q["id"]]["answer"] for q in s["questions"][:3]}
    r = svc.grade_session("u1", s["session_token"], answers)
    assert r["score"] == 3 and r["max_score"] == 4 and r["items"][0]["explanation"]
    with pytest.raises(svc.MockError):
        svc.grade_session("someone-else", s["session_token"], answers)


def test_count_is_capped_and_timer_validated():
    s = svc.start_session("u1", "essay", 99, 20)
    assert len(s["questions"]) == len(SECTIONS["essay"]["bank"])
    with pytest.raises(svc.MockError):
        svc.start_session("u1", "aptitude", 5, 0)


def test_late_submission_is_flagged(monkeypatch):
    s = svc.start_session("u1", "aptitude", 2, 1)
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 600)
    assert svc.grade_session("u1", s["session_token"], {})["submitted_late"] is True


def test_open_answers_use_a_labelled_rubric_without_llm():
    s = svc.start_session("u1", "essay", 1, 20)
    good = ("Firstly, technology changes how we learn. " * 8 + "\n\n" + "However, access is uneven in villages. " * 8
            + "\n\n" + "In conclusion, for example, cheap phones and local content can close the gap. " * 5)
    r = svc.grade_session("u1", s["session_token"], {s["questions"][0]["id"]: good})
    item = r["items"][0]
    assert item["method"] == "rubric" and item["ai_generated"] is False and item["score"] > 0 and item["stats"]["paragraphs"] == 3


async def test_api_students_only_one_submission_and_history(client, db_factory):
    student = await register_student(client)
    officer = await create_officer(client, db_factory)
    assert (await client.get("/api/v1/mock/sections")).status_code == 401
    assert (await client.get("/api/v1/mock/sections", headers=officer["headers"])).status_code == 403
    secs = (await client.get("/api/v1/mock/sections", headers=student["headers"])).json()
    assert {s["id"] for s in secs} == {"aptitude", "verbal", "cs_fundamentals", "coding", "spoken_english", "essay"}

    start = (await client.post("/api/v1/mock/start", json={"section": "coding", "count": 2, "minutes": 30},
                               headers=student["headers"])).json()
    assert len(start["questions"]) == 2 and "test_cases" not in start["questions"][0]
    answers = {q["id"]: REFERENCE[q["id"]] for q in start["questions"]}
    body = {"session_token": start["session_token"], "answers": answers}
    r = await client.post("/api/v1/mock/submit", json=body, headers=student["headers"])
    assert r.status_code == 200 and r.json()["percentage"] == 100.0
    assert (await client.post("/api/v1/mock/submit", json=body, headers=student["headers"])).status_code == 409

    other = await register_student(client)
    assert (await client.post("/api/v1/mock/submit", json=body, headers=other["headers"])).status_code in (409, 422)
    hist = (await client.get("/api/v1/mock/history", headers=student["headers"])).json()
    assert hist[0]["section"] == "coding" and hist[0]["percentage"] == 100.0 and "session" not in hist[0]
