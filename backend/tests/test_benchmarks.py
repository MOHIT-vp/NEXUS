"""Placement Cell edits the skill benchmark library; the next analysis uses the new requirements."""
from sqlalchemy import select

from tests.support import SOFTWARE_RESUME, create_officer, grant, register_student, upload


async def test_benchmark_editing_is_officer_only_and_audited(client, db_factory, reference_data):
    officer = await create_officer(client, db_factory)
    student = await register_student(client)
    assert (await client.get("/api/v1/benchmarks", headers=student["headers"])).status_code == 403
    roles = (await client.get("/api/v1/benchmarks", headers=officer["headers"])).json()
    se = next(r for r in roles if r["role_key"] == "software_engineer")
    assert se["skills"] and {s["importance"] for s in se["skills"]} <= {"required", "preferred"}

    body = {"skill": "Rust", "expected_level": "beginner", "importance": "preferred"}
    assert (await client.post("/api/v1/benchmarks/software_engineer", json=body, headers=student["headers"])).status_code == 403
    assert (await client.post("/api/v1/benchmarks/not_a_role", json=body, headers=officer["headers"])).status_code == 404
    assert (await client.post("/api/v1/benchmarks/software_engineer", json={**body, "expected_level": "guru"},
                              headers=officer["headers"])).status_code == 422
    added = await client.post("/api/v1/benchmarks/software_engineer", json=body, headers=officer["headers"])
    assert added.status_code == 201 and added.json()["source"].startswith("Placement Cell")
    assert (await client.post("/api/v1/benchmarks/software_engineer", json=body, headers=officer["headers"])).status_code == 409

    item = added.json()["id"]
    upd = await client.patch(f"/api/v1/benchmarks/item/{item}", headers=officer["headers"],
                             json={"expected_level": "intermediate", "importance": "required", "source": "TPO meeting, Oct 2026"})
    assert upd.status_code == 200 and upd.json()["importance"] == "required" and upd.json()["source"] == "TPO meeting, Oct 2026"
    assert (await client.patch(f"/api/v1/benchmarks/item/{item}", json={"importance": "maybe"},
                               headers=officer["headers"])).status_code == 422
    assert (await client.delete(f"/api/v1/benchmarks/item/{item}", headers=officer["headers"])).status_code == 204

    from app.models.workflow import AuditLog
    async with db_factory() as db:
        actions = (await db.execute(select(AuditLog.action).where(AuditLog.entity_type == "skill_benchmark"))).scalars().all()
    assert {"BENCHMARK_ADDED", "BENCHMARK_UPDATED", "BENCHMARK_REMOVED"} <= set(actions)


async def test_next_analysis_uses_the_edited_benchmark(client, db_factory, reference_data):
    officer = await create_officer(client, db_factory)
    await client.post("/api/v1/benchmarks/software_engineer", headers=officer["headers"],
                      json={"skill": "Rust", "expected_level": "intermediate", "importance": "required", "source": "TPO 2026"})
    s = await register_student(client)
    await grant(client, s["headers"], "resume_processing")
    run_id = (await upload(client, s["headers"], SOFTWARE_RESUME)).json()["run_id"]
    report = (await client.get(f"/api/v1/approvals/{run_id}/report", headers=officer["headers"])).json()
    gaps = {g["skill"]: g for g in report["result_snapshot"]["skill_gap_report"]["gaps"]}
    assert "Rust" in gaps and gaps["Rust"]["importance"] == "required" and gaps["Rust"]["benchmark_source"] == "TPO 2026"


def test_every_benchmark_and_sample_drive_skill_has_a_learning_resource():
    """Otherwise RETRIEVAL_GROUNDED fails and the plan needs an officer override."""
    from app.core.skills import canonical
    from app.services.reference_data import BENCHMARKS, LEARNING_RESOURCES
    from scripts._sample_drives import SAMPLE_DRIVES
    have = {canonical(k) for k in LEARNING_RESOURCES}
    needed = {canonical(r[0]): r[0] for rows in BENCHMARKS.values() for r in rows}
    for d in SAMPLE_DRIVES:
        needed.update({canonical(s): s for s in d["required_skills"] + d["preferred_skills"]})
    missing = sorted(v for k, v in needed.items() if k not in have)
    assert not missing, f"No learning resource for: {missing}"
