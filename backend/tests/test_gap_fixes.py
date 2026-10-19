"""
Tests for the ten gaps identified against Chapter 9:
approval security, per-source consent, real data, connectors, domain specialists,
retrieval, approve/edit/override/rollback, clarifying questions, validation gate,
upload ownership, dynamic target roles and the assembled draft.
"""
import uuid

from sqlalchemy import select

from tests.support import (
    CORE_RESUME, SOFTWARE_RESUME, create_officer, grant, register_student, upload,
)

NEW_DRIVE = {
    "name": "Northwind Systems", "role_title": "Software Engineer", "role_family": "software_engineering",
    "package_lpa": 9.5, "min_cgpa": 7.0, "required_skills": ["Python", "SQL", "Data Structures", "Git"],
    "preferred_skills": ["Docker"],
}


async def _student_with_run(client, roles=("software_engineer",), text=SOFTWARE_RESUME, extra_consents=(), **form):
    s = await register_student(client)
    await grant(client, s["headers"], "resume_processing", *extra_consents)
    r = await upload(client, s["headers"], text, roles=roles, **form)
    assert r.status_code == 200, r.text
    return s, r.json()


# 1. Approval endpoints require a Placement Cell login ---------------------------

async def test_approval_endpoints_require_officer(client, db_factory, reference_data):
    s, run = await _student_with_run(client)
    rid = run["run_id"]
    for method, path, body in [("get", "/api/v1/approvals/queue/open", None), ("get", f"/api/v1/approvals/{rid}/report", None),
                               ("post", f"/api/v1/approvals/{rid}/decide", {"decision": "approved"})]:
        kw = {"json": body} if body else {}
        assert (await getattr(client, method)(path, **kw)).status_code == 401
        assert (await getattr(client, method)(path, headers=s["headers"], **kw)).status_code == 403
    officer = await create_officer(client, db_factory)
    assert (await client.get("/api/v1/approvals/queue/open", headers=officer["headers"])).status_code == 200


async def test_registration_cannot_create_officer(client):
    r = await client.post("/api/v1/auth/register", json={"email": "x@college.edu", "password": "Passw0rd!x",
                                                          "full_name": "X", "role": "placement_officer"})
    assert r.status_code == 422


# 2. Consent read from the Consent table, per source ------------------------------

async def test_upload_blocked_without_resume_consent(client, reference_data):
    s = await register_student(client)
    assert (await upload(client, s["headers"])).status_code == 409
    await grant(client, s["headers"], "resume_processing")
    await client.post("/api/v1/consents/me/revoke", json={"consent_type": "resume_processing"}, headers=s["headers"])
    assert (await upload(client, s["headers"])).status_code == 409


def test_consent_node_reads_status_and_blocks():
    from app.agents.graph import consent_router, consent_validation_node
    from app.connectors.hub import registered_hub
    from tests.fakes import FakeHub, granted
    with registered_hub("c1", FakeHub(consents=granted("github"))):
        out = consent_validation_node({"run_id": "c1", "student_id": "s"})
    assert out["consent_validated"] is False and consent_router(out) == "blocked"


async def test_coding_data_not_collected_without_source_consent(client, db_factory, reference_data, fake_platforms):
    fake_platforms["github"]["asha-dev"] = ("ok", None)
    s, run = await _student_with_run(client, github_username="asha-dev")   # no github consent
    assert ("github", "asha-dev") not in fake_platforms["calls"]
    officer = await create_officer(client, db_factory)
    snap = (await client.get(f"/api/v1/approvals/{run['run_id']}/report", headers=officer["headers"])).json()["result_snapshot"]
    gh = next(x for x in snap["coding_analytics"]["sources"] if x["source"] == "github")
    assert gh["status"] == "not_consented" and gh["data"] is None


# 3/4. Real, personal data through connectors -------------------------------------

async def test_coding_stats_are_personal_not_fixed(client, db_factory, reference_data, fake_platforms):
    fake_platforms["leetcode"]["asha_codes"] = ("ok", None)
    fake_platforms["leetcode"]["ravi_codes"] = ("ok", None)
    fake_platforms["leetcode_totals"] = {"asha_codes": 214, "ravi_codes": 402}
    officer = await create_officer(client, db_factory)
    totals = []
    for handle, text in (("asha_codes", SOFTWARE_RESUME), ("ravi_codes", CORE_RESUME)):
        _, run = await _student_with_run(client, text=text, extra_consents=("leetcode",), leetcode_handle=handle)
        snap = (await client.get(f"/api/v1/approvals/{run['run_id']}/report", headers=officer["headers"])).json()["result_snapshot"]
        totals.append(snap["coding_analytics"]["summary"]["total_solved"])
        assert snap["metadata"]["coding_solved"] == totals[-1]
    assert totals == [214, 402] and 187 not in totals


async def test_unavailable_source_is_marked_not_faked(client, db_factory, reference_data, fake_platforms):
    fake_platforms["leetcode"]["asha_codes"] = ("unavailable", "LeetCode timed out")
    _, run = await _student_with_run(client, extra_consents=("leetcode",), leetcode_handle="asha_codes")
    officer = await create_officer(client, db_factory)
    snap = (await client.get(f"/api/v1/approvals/{run['run_id']}/report", headers=officer["headers"])).json()["result_snapshot"]
    assert snap["coding_analytics"]["status"] == "unavailable"
    assert "total_solved" not in snap["coding_analytics"]["summary"]


async def test_jobs_and_requirements_come_from_database(client, db_factory, reference_data):
    officer = await create_officer(client, db_factory)
    assert (await client.post("/api/v1/companies", json=NEW_DRIVE, headers=officer["headers"])).status_code == 201
    _, run = await _student_with_run(client)
    snap = (await client.get(f"/api/v1/approvals/{run['run_id']}/report", headers=officer["headers"])).json()["result_snapshot"]
    names = [m["company_name"] for m in snap["matching_result"]["matches"]]
    assert names == ["Northwind Systems"]                       # only the real listing, no mock list
    sources = {r["source"] for r in snap["role_requirements"][0]["requirements"]}
    assert any("Benchmark Library" in s for s in sources)       # requirements from the database


def test_agents_use_connectors():
    """Every data-facing agent reaches its data through the connector hub."""
    from app.agents.graph import agent_runner
    from app.connectors.hub import registered_hub
    from tests.fakes import FakeHub, job
    hub = FakeHub(jobs=[job()])
    with registered_hub("hub-run", hub):
        agent_runner.invoke({"run_id": "hub-run", "student_id": "s", "target_roles": ["software_engineer"],
                             "resume_data": {"raw_text": SOFTWARE_RESUME}, "errors": [], "audit_events": [],
                             "evidence_records": [], "retry_count": 0, "max_retries": 3, "budget_remaining": 100000},
                            config={"configurable": {"thread_id": "hub-run"}})
    assert {"consent", "coding.leetcode", "coding.github"} <= set(hub.calls)


# 5. Domain specialists change the output -----------------------------------------

def test_domain_specialists_change_recommendations():
    from app.agents.domain_specialist_agent import domain_specialist_node
    def ctx(roles):
        return {"target_roles": roles, "student_profile": {"skills": [{"name": "Python"}], "projects": []},
                "coding_analytics": {"summary": {"data_available": False}}}
    sw = domain_specialist_node(ctx(["software_engineer"]))["specialist_analysis"]
    core = domain_specialist_node(ctx(["mechanical_design_engineer"]))["specialist_analysis"]
    t = lambda a: {r["title"] for s in a["specialists"] for r in s["recommendations"]}
    assert sw["selected_domains"] == ["software"] and core["selected_domains"] == ["core"]
    assert t(sw).isdisjoint(t(core))
    assert sw["scoring_weights"] != core["scoring_weights"]


# 6. Retrieval is used and cited --------------------------------------------------

async def test_roadmap_cites_knowledge_base(client, db_factory, reference_data):
    _, run = await _student_with_run(client)
    officer = await create_officer(client, db_factory)
    snap = (await client.get(f"/api/v1/approvals/{run['run_id']}/report", headers=officer["headers"])).json()["result_snapshot"]
    assert snap["retrieval"]["roadmap_citations"]
    assert any(i["resource_status"] == "cited" for i in snap["roadmap"]["items"])


# 7. Approve / edit / override / rollback -----------------------------------------

async def test_edit_override_and_rollback(client, db_factory, reference_data):
    officer = await create_officer(client, db_factory)
    await client.post("/api/v1/companies", json=NEW_DRIVE, headers=officer["headers"])
    s, run1 = await _student_with_run(client)
    rid = run1["run_id"]
    report = (await client.get(f"/api/v1/approvals/{rid}/report", headers=officer["headers"])).json()
    gap = report["result_snapshot"]["skill_gap_report"]["gaps"][0]["skill"]

    r = await client.post(f"/api/v1/approvals/{rid}/edit", headers=officer["headers"],
                          json={"officer_note": "Practise DSA daily", "gap_recommendations": {gap: f"Do 2 {gap} problems a day."}})
    assert r.status_code == 200 and r.json()["status"] == "pending_review"

    warnings = report["validation_report"]["checks"]
    has_warning = any(not c["passed"] and c["severity"] == "warning" for c in warnings)
    if has_warning:
        assert (await client.post(f"/api/v1/approvals/{rid}/decide", json={"decision": "approved"},
                                  headers=officer["headers"])).status_code == 409
        assert (await client.post(f"/api/v1/approvals/{rid}/override", json={"reason": "short"},
                                  headers=officer["headers"])).status_code == 422
        r = await client.post(f"/api/v1/approvals/{rid}/override", headers=officer["headers"],
                              json={"reason": "Reviewed manually; resources shared in class."})
    else:
        r = await client.post(f"/api/v1/approvals/{rid}/decide", json={"decision": "approved"}, headers=officer["headers"])
    assert r.status_code == 200 and r.json()["status"] == "published"

    # second plan, then roll back to the first
    _, run2 = await _student_with_run_same(client, s)
    await client.post(f"/api/v1/approvals/{run2}/override", headers=officer["headers"],
                      json={"reason": "Reviewed manually; resources shared in class."})
    await client.post(f"/api/v1/approvals/{run2}/decide", json={"decision": "approved"}, headers=officer["headers"])
    queue = (await client.get("/api/v1/approvals/queue/open", headers=officer["headers"])).json()
    target = next(d["rollback_to_version_id"] for d in queue["recent_decisions"] if d["run_id"] == run2 and d["rollback_to_version_id"])
    # Re-checked first: refused while the student has withdrawn resume consent
    assert (await client.post("/api/v1/consents/me/revoke", json={"consent_type": "resume_processing"},
                              headers=s["headers"])).status_code == 200
    r = await client.post(f"/api/v1/versions/{target}/rollback", headers=officer["headers"])
    assert r.status_code == 409 and "consent" in r.json()["detail"]["message"]
    await grant(client, s["headers"], "resume_processing")
    r = await client.post(f"/api/v1/versions/{target}/rollback", headers=officer["headers"])
    assert r.status_code == 200 and r.json()["active_version_number"] == 1
    assert (await client.post(f"/api/v1/versions/{target}/rollback", headers=s["headers"])).status_code == 403


async def _student_with_run_same(client, s):
    r = await upload(client, s["headers"], SOFTWARE_RESUME)
    assert r.status_code == 200, r.text
    return s, r.json()["run_id"]


# 8. Clarifying questions and revision --------------------------------------------

async def test_planner_asks_and_revises(client):
    s = await register_student(client)
    r = (await client.post("/api/v1/planner/clarify", json={"request": "help me get placed"}, headers=s["headers"])).json()
    assert r["status"] == "needs_clarification" and len(r["questions"]) >= 2
    r = (await client.post("/api/v1/planner/clarify", headers=s["headers"], json={
        "request": "help me get placed", "slots": r["slots"],
        "answers": {"target_roles": ["Software Engineer"], "skill_level": "Beginner", "timeline": "12 weeks", "priorities": "DSA"}})).json()
    assert r["status"] == "draft_ready" and r["plan"]["target_roles"] == ["software_engineer"]
    r = (await client.post("/api/v1/planner/clarify", headers=s["headers"], json={
        "request": "help me get placed", "slots": r["slots"], "feedback": "switch to data analyst instead"})).json()
    assert r["plan"]["target_roles"] == ["data_analyst"] and r["changes"]
    specific = (await client.post("/api/v1/planner/clarify", headers=s["headers"], json={
        "request": "intermediate, Data Analyst in 8 weeks, prioritising SQL"})).json()
    assert specific["status"] == "draft_ready"


# 9. Failed validation never reaches the officer ----------------------------------

async def test_failed_validation_is_not_queued(client, db_factory, reference_data):
    s, run = await _student_with_run(client, roles=("Space Tourism Guide",))
    assert run["status"] == "validation_failed"
    status = (await client.get(f"/api/v1/process/status/{run['run_id']}", headers=s["headers"])).json()
    assert any(f["code"] == "REQUIREMENTS_VERIFIED" for f in status["validation_failures"])
    officer = await create_officer(client, db_factory)
    queue = (await client.get("/api/v1/approvals/queue/open", headers=officer["headers"])).json()
    assert run["run_id"] not in [r["run_id"] for r in queue["pending_runs"]]
    assert (await client.post(f"/api/v1/approvals/{run['run_id']}/decide", json={"decision": "approved"},
                              headers=officer["headers"])).status_code == 409


# 10. Ownership, target roles, assembled draft ------------------------------------

async def test_upload_owned_by_student_with_roles_and_draft(client, db_factory, reference_data):
    from app.models.user import Student
    from app.models.workflow import WorkflowRun
    s, run = await _student_with_run(client, roles=("data_analyst",))
    async with db_factory() as db:
        row = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == uuid.UUID(run["run_id"])))).scalar_one()
        owner = (await db.execute(select(Student.user_id).where(Student.id == row.student_id))).scalar_one()
    assert str(owner) == s["user_id"]
    snap = row.result_snapshot
    assert snap["target_roles"] == ["data_analyst"]
    for section in ("student_profile", "skill_gap_report", "coding_analytics", "specialist_analysis",
                    "matching_result", "roadmap", "retrieval", "validation_report"):
        assert snap.get(section) is not None, section
    other = await register_student(client)
    assert (await client.get(f"/api/v1/process/status/{run['run_id']}", headers=other["headers"])).status_code == 404
    assert (await client.get(f"/api/v1/dashboard/student/{run['run_id']}", headers=other["headers"])).status_code == 404


async def test_upload_requires_target_role(client):
    s = await register_student(client)
    await grant(client, s["headers"], "resume_processing")
    assert (await upload(client, s["headers"], roles=())).status_code == 409


# Lab 8: Placement Cell batch re-run ------------------------------------------------

async def test_batch_rerun_is_officer_only_and_uses_each_students_data(client, db_factory, reference_data):
    officer = await create_officer(client, db_factory)
    a, run_a = await _student_with_run(client)
    b, _ = await _student_with_run(client, roles=("mechanical_design_engineer",), text=CORE_RESUME)
    no_resume = await register_student(client)
    async with db_factory() as db:
        from app.models.user import Student
        ids = {k: str((await db.execute(select(Student.id).where(Student.user_id == uuid.UUID(v["user_id"])))).scalar_one())
               for k, v in {"a": a, "b": b, "none": no_resume}.items()}

    body = {"student_ids": list(ids.values())}
    assert (await client.post("/api/v1/workflows/batch", json=body)).status_code == 401
    assert (await client.post("/api/v1/workflows/batch", json=body, headers=a["headers"])).status_code == 403

    # Student b withdraws consent: they are skipped, never processed
    await client.post("/api/v1/consents/me/revoke", json={"consent_type": "resume_processing"}, headers=b["headers"])
    r = await client.post("/api/v1/workflows/batch", json=body, headers=officer["headers"])
    assert r.status_code == 200, r.text
    by_id = {x["student_id"]: x for x in r.json()["results"]}
    assert by_id[ids["a"]]["status"] in ("pending_review", "validation_failed") and by_id[ids["a"]]["run_id"] != run_a["run_id"]
    assert by_id[ids["b"]]["status"] == "skipped" and "consent" in by_id[ids["b"]]["reason"]
    assert by_id[ids["none"]]["status"] == "skipped"

    # The new run carries the student's own roles; the student can see it, others can't
    new_run = by_id[ids["a"]]["run_id"]
    status_ = await client.get(f"/api/v1/process/status/{new_run}", headers=a["headers"])
    assert status_.status_code == 200
    assert (await client.get(f"/api/v1/process/status/{new_run}", headers=no_resume["headers"])).status_code == 404

    one = await client.post("/api/v1/workflows/start", json={"student_id": ids["none"]}, headers=officer["headers"])
    assert one.status_code == 409


# Sign-out is enforced by the server ---------------------------------------------

async def test_logout_revokes_token_server_side(client):
    s = await register_student(client)
    assert (await client.get("/api/v1/auth/me", headers=s["headers"])).status_code == 200
    assert (await client.post("/api/v1/auth/logout", headers=s["headers"])).status_code == 204
    r = await client.get("/api/v1/auth/me", headers=s["headers"])
    assert r.status_code == 401 and "Signed out" in r.json()["detail"]
    # Signing in again issues a new, working token
    login = await client.post("/api/v1/auth/login", data={"username": s["email"], "password": "Student-Passw0rd"})
    fresh = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await client.get("/api/v1/auth/me", headers=fresh)).status_code == 200
    # Refresh tokens rotate: each works once
    first = await client.post("/api/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})
    assert first.status_code == 200
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})).status_code == 401
    login = await client.post("/api/v1/auth/login", data={"username": s["email"], "password": "Student-Passw0rd"})
    fresh = {"Authorization": f"Bearer {login.json()['access_token']}"}
    # A refresh token sent at logout is revoked too
    refresh = login.json()["refresh_token"]
    assert (await client.post("/api/v1/auth/logout", json={"refresh_token": refresh}, headers=fresh)).status_code == 204
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})).status_code == 401


# Admin: accounts and audit log (not approvals) ------------------------------------

async def test_admin_manages_accounts_but_cannot_approve(client, db_factory):
    from app.services.auth import create_user
    async with db_factory() as db:
        await create_user(db, email="root@college.edu", password="Admin-Passw0rd", full_name="Admin", role="admin")
        await db.commit()
    tok = (await client.post("/api/v1/auth/login", data={"username": "root@college.edu", "password": "Admin-Passw0rd"})).json()["access_token"]
    admin = {"Authorization": f"Bearer {tok}"}
    student = await register_student(client)

    assert (await client.get("/api/v1/admin/users", headers=student["headers"])).status_code == 403
    body = {"email": "tpo2@college.edu", "full_name": "New TPO", "password": "Tpo-Passw0rd", "role": "placement_officer"}
    assert (await client.post("/api/v1/admin/users", json={**body, "role": "student"}, headers=admin)).status_code == 422
    assert (await client.post("/api/v1/admin/users", json={**body, "password": "weakpassword"}, headers=admin)).status_code == 422
    created = await client.post("/api/v1/admin/users", json=body, headers=admin)
    assert created.status_code == 201
    assert (await client.post("/api/v1/admin/users", json=body, headers=admin)).status_code == 409

    # The new officer can sign in; once deactivated their token stops working
    otok = (await client.post("/api/v1/auth/login", data={"username": body["email"], "password": body["password"]})).json()["access_token"]
    officer = {"Authorization": f"Bearer {otok}"}
    assert (await client.get("/api/v1/approvals/queue/open", headers=officer)).status_code == 200
    r = await client.patch(f"/api/v1/admin/users/{created.json()['id']}", json={"is_active": False}, headers=admin)
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert (await client.get("/api/v1/approvals/queue/open", headers=officer)).status_code == 401

    # Admin cannot approve plans, and cannot lock themselves out
    assert (await client.get("/api/v1/approvals/queue/open", headers=admin)).status_code == 403
    assert (await client.post(f"/api/v1/approvals/{uuid.uuid4()}/decide", json={"decision": "approved"}, headers=admin)).status_code == 403
    me = (await client.get("/api/v1/auth/me", headers=admin)).json()["id"]
    assert (await client.patch(f"/api/v1/admin/users/{me}", json={"is_active": False}, headers=admin)).status_code == 409

    stats = (await client.get("/api/v1/admin/stats", headers=admin)).json()
    assert stats["users_by_role"]["student"] == 1
    actions = [e["action"] for e in (await client.get("/api/v1/admin/audit", headers=admin)).json()]
    assert "ACCOUNT_CREATED" in actions and "ACCOUNT_DEACTIVATED" in actions


# Lab 4: tag + similarity retrieval, and similar prior students ---------------------

def test_hashed_embeddings_rank_related_text_higher():
    from app.services.similarity import cosine, embed
    q = embed("python sql backend developer")
    assert cosine(q, embed("Backend developer with Python and SQL")) > cosine(q, embed("mechanical CAD design SolidWorks"))
    assert cosine(q, q) == 1.0


async def test_retrieval_reranks_by_similarity_and_falls_back(db_factory, reference_data):
    from app.agents.knowledge_base import kb
    async with db_factory() as db:
        res = await kb.retrieve(db, "SQL learning resource", doc_types=["learning_resource"], k=3)
        assert res.status == "ok" and res.backend == "postgres_fts+hashed"
        assert all(i.doc_type == "learning_resource" for i in res.items)          # tag filter respected
        assert [i.score for i in res.items] == sorted([i.score for i in res.items], reverse=True)
        assert "sql" in res.items[0].title.lower()


async def test_similar_prior_students_are_anonymised_and_exclude_self(client, db_factory, reference_data):
    officer = await create_officer(client, db_factory)
    first, run1 = await _student_with_run(client)
    rid = run1["run_id"]
    await client.post(f"/api/v1/approvals/{rid}/override", headers=officer["headers"],
                      json={"reason": "Reviewed manually; resources shared in class."})
    await client.post(f"/api/v1/approvals/{rid}/decide", json={"decision": "approved"}, headers=officer["headers"])

    other_resume = """Ravi Kumar
ravi.k@college.edu

Summary
Third-year information technology student interested in web platforms.

Technical Skills
Python, SQL, Git, Docker, JavaScript

Projects
Hostel Complaint Tracker
- Flask web app in Python with a SQL database, versioned in Git, shipped as a Docker image
Expense Splitter
- JavaScript single page app that stores data through a small Python service
"""
    second, run2 = await _student_with_run(client, text=other_resume)
    snap = (await client.get(f"/api/v1/approvals/{run2['run_id']}/report", headers=officer["headers"])).json()["result_snapshot"]
    similar = snap["retrieval"]["similar_prior_students"]
    assert len(similar) == 1 and similar[0]["similarity"] > 0.2 and "Python" in similar[0]["shared_skills"]
    assert set(similar[0]) == {"similarity", "target_roles", "shared_skills", "readiness_percentage", "top_gaps"}
    assert "Asha" not in str(similar)


# Interview Agent: mock-interview practice ------------------------------------------

async def test_mock_interview_practice_on_published_plan(client, db_factory, reference_data):
    officer = await create_officer(client, db_factory)
    s, run = await _student_with_run(client)
    assert (await client.get("/api/v1/interviews/practice", headers=s["headers"])).status_code == 404   # not published yet
    rid = run["run_id"]
    await client.post(f"/api/v1/approvals/{rid}/override", headers=officer["headers"],
                      json={"reason": "Reviewed manually; resources shared in class."})
    await client.post(f"/api/v1/approvals/{rid}/decide", json={"decision": "approved"}, headers=officer["headers"])

    qs = (await client.get("/api/v1/interviews/practice", headers=s["headers"])).json()["questions"]
    assert qs and {"index", "text", "type"} <= set(qs[0])
    skill = qs[0]["skill_targeted"] or "the topic"
    good = (f"{skill} is something I used in my project because it solved a real problem. For example I built a campus "
            f"API with 2000 users and used {skill} so that queries stayed fast instead of scanning everything; the result "
            "was a 40% faster page. I learned to measure first, then optimise, and to explain trade-offs to my team. ") * 2
    fb = (await client.post("/api/v1/interviews/practice", json={"question_index": 0, "answer": good}, headers=s["headers"])).json()
    weak = (await client.post("/api/v1/interviews/practice", json={"question_index": 0, "answer": "not sure"}, headers=s["headers"])).json()
    assert fb["method"] == "rubric" and fb["ai_generated"] is False and fb["score"] > weak["score"]
    assert weak["improvements"]
    assert (await client.post("/api/v1/interviews/practice", json={"question_index": 999, "answer": "x"},
                              headers=s["headers"])).status_code == 404
    assert (await client.get("/api/v1/interviews/practice", headers=officer["headers"])).status_code == 403


# No student sees another student's data --------------------------------------------

async def test_runs_evidence_versions_and_chat_are_scoped_to_owner(client, db_factory, reference_data):
    owner, run = await _student_with_run(client)
    other = await register_student(client)
    rid = run["run_id"]
    async with db_factory() as db:
        from app.models.user import Student
        sid = (await db.execute(select(Student.id).where(Student.user_id == uuid.UUID(owner["user_id"])))).scalar_one()

    assert (await client.get(f"/api/v1/process/status/{rid}", headers=other["headers"])).status_code == 404
    assert (await client.get(f"/api/v1/evidence/{rid}", headers=other["headers"])).status_code in (403, 404)
    assert (await client.get(f"/api/v1/versions/student/{sid}", headers=other["headers"])).status_code == 404
    assert (await client.get(f"/api/v1/versions/student/{sid}", headers=owner["headers"])).status_code == 200
    # The assistant is for signed-in students only
    assert (await client.post("/api/v1/chat", json={"message": "hi", "run_id": rid})).status_code == 401
    officer = await create_officer(client, db_factory)
    assert (await client.post("/api/v1/chat", json={"message": "hi"}, headers=officer["headers"])).status_code == 403


async def test_placement_cell_signup_needs_admin_approval(client, db_factory):
    from app.services.auth import create_user
    body = {"email": "newtpo@college.edu", "password": "Tpo-Passw0rd", "full_name": "New TPO"}
    r = await client.post("/api/v1/auth/register-placement-cell", json=body)
    assert r.status_code == 202
    assert (await client.post("/api/v1/auth/register-placement-cell", json=body)).status_code == 409
    login = await client.post("/api/v1/auth/login", data={"username": body["email"], "password": body["password"]})
    assert login.status_code == 403 and "approval" in login.json()["detail"]
    # wrong password still gives the generic message
    assert (await client.post("/api/v1/auth/login", data={"username": body["email"], "password": "Wrong-Pass1"})).status_code == 401

    async with db_factory() as db:
        await create_user(db, email="root2@college.edu", password="Admin-Passw0rd", full_name="Admin", role="admin")
        await db.commit()
    tok = (await client.post("/api/v1/auth/login", data={"username": "root2@college.edu", "password": "Admin-Passw0rd"})).json()["access_token"]
    admin = {"Authorization": f"Bearer {tok}"}
    pending = next(u for u in (await client.get("/api/v1/admin/users", headers=admin)).json() if u["email"] == body["email"])
    assert pending["is_active"] is False and pending["role"] == "placement_officer"
    await client.patch(f"/api/v1/admin/users/{pending['id']}", json={"is_active": True}, headers=admin)
    login = await client.post("/api/v1/auth/login", data={"username": body["email"], "password": body["password"]})
    assert login.status_code == 200 and login.json()["user"]["role"] == "placement_officer"
