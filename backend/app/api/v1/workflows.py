"""
Placement Cell batch re-runs (Lab 8).

An officer re-runs the agent pipeline for one or many students — e.g. after new
drives are listed — using each student's own latest resume, their last target
roles/plan/handles and their CURRENT consent records. Each student runs in its
own database session with bounded concurrency; results go to the review queue
exactly like a student upload (validated drafts only).
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import database
from app.api.deps import require_role
from app.models.profile import Resume
from app.models.user import Consent, Student, User
from app.models.workflow import AuditLog, WorkflowRun
from app.services.consent import consent_status, missing_required
from app.services.pipeline import ResumeError, resume_pipeline, run_pipeline, saved_progress

router = APIRouter(prefix="/workflows", tags=["Workflows"])

MAX_CONCURRENT_RUNS = 3


class WorkflowBatchRequest(BaseModel):
    student_ids: Optional[List[uuid.UUID]] = Field(None, description="Students to re-run; omit for every student with a resume")
    target_roles: Optional[List[str]] = Field(None, description="Override target roles; default: each student's last roles")


class WorkflowStartRequest(BaseModel):
    student_id: uuid.UUID
    target_roles: Optional[List[str]] = None


async def _run_one(student_id: uuid.UUID, roles_override: Optional[List[str]], officer_id: uuid.UUID) -> Dict[str, Any]:
    """Re-run one student in its own session. Never raises — the batch reports per-student outcomes."""
    async with database.async_session_factory() as db:
        try:
            student = (await db.execute(select(Student).where(Student.id == student_id))).scalar_one_or_none()
            if student is None:
                return {"student_id": str(student_id), "status": "skipped", "reason": "Student not found"}
            resume = (await db.execute(select(Resume).where(Resume.student_id == student.id)
                                       .order_by(Resume.created_at.desc()).limit(1))).scalar_one_or_none()
            if resume is None or not (resume.raw_text or "").strip():
                return {"student_id": str(student_id), "status": "skipped", "reason": "No uploaded resume"}
            consents = consent_status((await db.execute(select(Consent).where(Consent.student_id == student.id))).scalars().all())
            if missing_required(consents):
                return {"student_id": str(student_id), "status": "skipped", "reason": "Resume consent not granted"}

            last = (await db.execute(select(WorkflowRun).where(WorkflowRun.student_id == student.id,
                                                               WorkflowRun.result_snapshot.isnot(None))
                                     .order_by(WorkflowRun.created_at.desc()).limit(1))).scalar_one_or_none()
            snap = (last.result_snapshot or {}) if last else {}
            meta = snap.get("metadata") or {}
            roles = roles_override or snap.get("target_roles") or []
            if not roles:
                return {"student_id": str(student_id), "status": "skipped", "reason": "No target roles on record"}
            plan = snap.get("request") if isinstance(snap.get("request"), dict) else {"target_roles": roles}
            plan = {**plan, "target_roles": roles}

            officer = (await db.execute(select(User).where(User.id == officer_id))).scalar_one()
            db_run = WorkflowRun(student_id=student.id, initiated_by=officer.id, status="running", current_step="init",
                                 started_at=datetime.now(timezone.utc))
            db.add(db_run)
            await db.flush()
            db.add(AuditLog(actor_id=officer.id, actor_type="placement_officer", workflow_run_id=db_run.id,
                            action="BATCH_RERUN_STARTED", entity_type="workflow_run", entity_id=db_run.id,
                            correlation_id=uuid.uuid4(), details={"target_roles": roles}))
            await db.commit()

            passed = await run_pipeline(
                db, db_run=db_run, student=student, actor=officer, consents=consents, roles=roles, plan=plan,
                handles={"github": meta.get("github_username"), "leetcode": meta.get("leetcode_handle")},
                cgpa=meta.get("cgpa"), coding_solved=meta.get("self_reported_coding_solved") or 0,
                resume_data={"file_path": None, "file_name": resume.file_name, "mime_type": resume.mime_type,
                             "raw_text": resume.raw_text, "resume_id": str(resume.id), "is_duplicate": False},
            )
            return {"student_id": str(student_id), "run_id": str(db_run.id), "status": db_run.status,
                    "validation_passed": passed}
        except Exception as exc:  # one student's failure must not stop the batch
            await db.rollback()
            return {"student_id": str(student_id), "status": "failed", "reason": exc.__class__.__name__}


async def _batch(student_ids: List[uuid.UUID], roles: Optional[List[str]], officer: User) -> List[Dict[str, Any]]:
    gate = asyncio.Semaphore(MAX_CONCURRENT_RUNS)

    async def guarded(sid):
        async with gate:
            return await _run_one(sid, roles, officer.id)

    return list(await asyncio.gather(*(guarded(s) for s in student_ids)))


@router.post("/batch", response_model=Dict[str, Any])
async def start_batch_workflows(
    request: WorkflowBatchRequest,
    officer: User = Depends(require_role("placement_officer")),
):
    """Re-run the pipeline for many students at once (Placement Cell only)."""
    ids = request.student_ids
    if not ids:
        async with database.async_session_factory() as db:
            ids = list((await db.execute(select(Resume.student_id).distinct())).scalars().all())
    results = await _batch(ids, request.target_roles, officer)
    summary: Dict[str, int] = {}
    for r in results:
        summary[r["status"]] = summary.get(r["status"], 0) + 1
    return {"batch_size": len(ids), "max_concurrency": MAX_CONCURRENT_RUNS, "summary": summary, "results": results}


@router.post("/start", response_model=Dict[str, Any])
async def start_workflow(
    request: WorkflowStartRequest,
    officer: User = Depends(require_role("placement_officer")),
):
    """Re-run one student (a batch of one)."""
    result = (await _batch([request.student_id], request.target_roles, officer))[0]
    if result["status"] == "skipped":
        raise HTTPException(status_code=409, detail=result["reason"])
    return result


@router.get("/{run_id}/progress", response_model=Dict[str, Any])
async def run_progress(
    run_id: uuid.UUID,
    officer: User = Depends(require_role("placement_officer")),
):
    """Which steps a run has completed (from its saved checkpoint) and what runs next."""
    progress = saved_progress(str(run_id))
    events = progress["values"].get("audit_events") or []
    return {"run_id": str(run_id), "has_saved_progress": bool(progress["values"]),
            "completed_step": progress["values"].get("current_step"), "next": progress["next"],
            "completed_agents": [getattr(e, "agent", None) or (e.get("agent") if isinstance(e, dict) else None) for e in events]}


@router.post("/{run_id}/resume", response_model=Dict[str, Any])
async def resume_run(
    run_id: uuid.UUID,
    officer: User = Depends(require_role("placement_officer")),
):
    """Continue an interrupted or failed run from its last completed step (Placement Cell only)."""
    async with database.async_session_factory() as db:
        run = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))).scalar_one_or_none()
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        resumed_from = saved_progress(str(run_id))["next"]
        try:
            passed = await resume_pipeline(db, db_run=run, actor=officer)
        except ResumeError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return {"run_id": str(run.id), "status": run.status, "validation_passed": passed, "resumed_from": resumed_from}
