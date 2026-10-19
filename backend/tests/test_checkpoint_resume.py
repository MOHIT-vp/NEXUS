"""Lab 6: a run interrupted part-way resumes from its last saved step instead of starting over."""
import uuid

import pytest
from sqlalchemy import select

from tests.support import SOFTWARE_RESUME, create_officer, grant, register_student, upload


def _crash_job_matching_once(monkeypatch):
    """The job listings source fails once (e.g. the database connection drops mid-run)."""
    from app.connectors import job_connector, role_connector
    calls = {"jobs": 0, "roles": 0}
    real_jobs = job_connector.JobConnector.list_active_jobs
    real_roles = role_connector.RoleConnector.get_role_requirements

    async def flaky_jobs(self):
        calls["jobs"] += 1
        if calls["jobs"] == 1:
            raise RuntimeError("connection to the jobs database was lost")
        return await real_jobs(self)

    async def counted_roles(self, roles):
        calls["roles"] += 1
        return await real_roles(self, roles)

    monkeypatch.setattr(job_connector.JobConnector, "list_active_jobs", flaky_jobs)
    monkeypatch.setattr(role_connector.RoleConnector, "get_role_requirements", counted_roles)
    return calls


async def _crashed_run(client, db_factory, monkeypatch, text=SOFTWARE_RESUME):
    calls = _crash_job_matching_once(monkeypatch)
    s = await register_student(client)
    await grant(client, s["headers"], "resume_processing")
    with pytest.raises(RuntimeError):
        await upload(client, s["headers"], text)
    from app.models.workflow import WorkflowRun
    async with db_factory() as db:
        run = (await db.execute(select(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(1))).scalar_one()
    return s, run, calls


async def test_failed_run_resumes_from_where_it_stopped(client, db_factory, reference_data, monkeypatch):
    from app.services.pipeline import saved_progress
    officer = await create_officer(client, db_factory)
    s, run, calls = await _crashed_run(client, db_factory, monkeypatch)
    assert run.status == "failed"

    progress = saved_progress(str(run.id))
    assert progress["next"] == ["job_matching_agent"]          # everything before it is saved
    assert progress["values"]["skill_gap_report"] and progress["values"]["student_profile"]
    roles_calls_before = calls["roles"]

    view = (await client.get(f"/api/v1/workflows/{run.id}/progress", headers=officer["headers"])).json()
    assert view["has_saved_progress"] and view["next"] == ["job_matching_agent"]
    assert "SkillGapAgent" in view["completed_agents"]

    assert (await client.post(f"/api/v1/workflows/{run.id}/resume", headers=s["headers"])).status_code == 403
    r = await client.post(f"/api/v1/workflows/{run.id}/resume", headers=officer["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["resumed_from"] == ["job_matching_agent"]
    assert body["status"] in ("pending_review", "validation_failed")
    assert calls["roles"] == roles_calls_before                  # skill-gap step was not repeated

    from app.models.workflow import AuditLog, WorkflowRun
    async with db_factory() as db:
        done = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == run.id))).scalar_one()
        assert done.result_snapshot and done.result_snapshot["matching_result"]
        actions = (await db.execute(select(AuditLog.action).where(AuditLog.workflow_run_id == run.id))).scalars().all()
        assert "PIPELINE_FAILED" in actions and "RUN_RESUMED" in actions

    again = await client.post(f"/api/v1/workflows/{run.id}/resume", headers=officer["headers"])
    assert again.status_code == 409 and "already finished" in again.json()["detail"]


async def test_runs_cut_off_by_a_restart_resume_on_startup(client, db_factory, reference_data, monkeypatch):
    from app.models.workflow import WorkflowRun
    from app.services.pipeline import resume_interrupted_runs
    _, run, _ = await _crashed_run(client, db_factory, monkeypatch)
    async with db_factory() as db:   # a hard crash leaves the run marked 'running'
        r = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == run.id))).scalar_one()
        r.status = "running"
        await db.commit()
    outcomes = await resume_interrupted_runs()
    assert outcomes[0]["run_id"] == str(run.id) and outcomes[0]["status"] in ("pending_review", "validation_failed")


async def test_resume_refused_without_saved_progress_or_consent(client, db_factory, reference_data, monkeypatch):
    officer = await create_officer(client, db_factory)
    assert (await client.post(f"/api/v1/workflows/{uuid.uuid4()}/resume", headers=officer["headers"])).status_code == 404
    s, run, _ = await _crashed_run(client, db_factory, monkeypatch)
    await client.post("/api/v1/consents/me/revoke", json={"consent_type": "resume_processing"}, headers=s["headers"])
    r = await client.post(f"/api/v1/workflows/{run.id}/resume", headers=officer["headers"])
    assert r.status_code == 409 and "consent" in r.json()["detail"]


# Lab 8: best-of-N roadmap selected by plan alignment ---------------------------------

def _item(skill, priority, hours, student_priority=False):
    return {"skill": skill, "addresses_gap": skill, "priority": priority, "estimated_hours": hours,
            "student_priority": student_priority}


GAPS = [{"skill": "SQL", "importance": "required", "severity": "critical"},
        {"skill": "Operating Systems", "importance": "required", "severity": "critical"},
        {"skill": "Docker", "importance": "preferred", "severity": "medium"},
        {"skill": "Kubernetes", "importance": "preferred", "severity": "medium"}]


def test_selector_scores_every_candidate_and_keeps_required_gaps():
    from app.agents.roadmap_selector import STRATEGIES, select_best_roadmap
    items = [_item("Docker", "medium", 12), _item("SQL", "critical", 30), _item("Kubernetes", "medium", 12),
             _item("Operating Systems", "critical", 30)]
    out = select_best_roadmap(items, GAPS, priorities=[], weeks=4)       # 60 h budget at 15 h/week
    sel = out["selection"]
    assert {c["strategy"] for c in sel["candidates"]} == set(STRATEGIES)
    assert sel["candidates"][0]["strategy"] == sel["selected"]
    skills = [i["skill"] for i in out["items"]]
    assert {"SQL", "Operating Systems"} <= set(skills)                   # required gaps never dropped
    assert skills.index("SQL") < (skills.index("Docker") if "Docker" in skills else 99)
    assert sel["selected"] == "fit_timeline" and sum(i["estimated_hours"] for i in out["items"]) <= 60


def test_selector_prefers_the_students_priorities_when_given():
    from app.agents.roadmap_selector import select_best_roadmap
    items = [_item("SQL", "critical", 30), _item("Operating Systems", "critical", 30),
             _item("Docker", "medium", 12, student_priority=True)]
    out = select_best_roadmap(items, GAPS, priorities=["docker"], weeks=None)
    by = {c["strategy"]: c for c in out["selection"]["candidates"]}
    assert by["student_priorities_first"]["breakdown"]["student_priorities"] > by["gaps_first"]["breakdown"]["student_priorities"]


async def test_pipeline_records_roadmap_selection(client, db_factory, reference_data):
    s = await register_student(client)
    await grant(client, s["headers"], "resume_processing")
    run_id = (await upload(client, s["headers"], SOFTWARE_RESUME)).json()["run_id"]
    from app.models.workflow import WorkflowRun
    async with db_factory() as db:
        snap = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == uuid.UUID(run_id)))).scalar_one().result_snapshot
    sel = snap["roadmap"]["selection"]
    assert sel["method"] == "best_of_n_by_plan_alignment" and len(sel["candidates"]) == 4 and sel["score"] > 0
