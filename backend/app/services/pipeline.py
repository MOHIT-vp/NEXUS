"""
The agent pipeline for one student run — shared by resume upload and the
Placement Cell's batch re-run (Lab 8).

Runs the LangGraph graph in a worker thread with a connector hub registered,
stores the assembled draft as the run's result snapshot, and sets the status:
pending_review when every required check passed, validation_failed otherwise.

Lab 6: the graph saves its progress after every node (see graph.make_checkpointer).
A run interrupted part-way — a crash, a restart, a failing connector — is
continued with `resume_pipeline`, which picks up after the last completed step.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import agent_runner
from app.connectors.hub import DatabaseConnectorHub, registered_hub
from app.models.user import Consent, Student, User
from app.models.workflow import AuditLog, WorkflowRun
from app.services.audit import log_workflow_events
from app.services.consent import consent_status, is_granted, missing_required
from app.services.resume_perfection_service import generate_resume_perfection_questions


class ResumeError(RuntimeError):
    """The run can't be resumed (nothing saved, already finished, or consent withdrawn)."""


def _config(run_id: str) -> Dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}


def _invoke_graph(initial_state: Optional[Dict[str, Any]], run_id: str, hub: Any) -> Dict[str, Any]:
    """Run the graph; with initial_state=None it continues from the last saved step."""
    with registered_hub(run_id, hub):
        return agent_runner.invoke(initial_state, config=_config(run_id))


def saved_progress(run_id: str) -> Dict[str, Any]:
    """What the checkpoint holds for a run: the completed state and the next node(s) to run."""
    snap = agent_runner.get_state(_config(run_id))
    return {"values": dict(snap.values or {}), "next": list(snap.next or [])}


async def _fail(db: AsyncSession, db_run: WorkflowRun, error: Exception) -> None:
    db_run.status = "failed"
    db_run.error_message = str(error)
    db_run.completed_at = datetime.now(timezone.utc)
    db.add(AuditLog(actor_type="system", workflow_run_id=db_run.id, action="PIPELINE_FAILED",
                    entity_type="workflow_run", entity_id=db_run.id, correlation_id=uuid.uuid4(),
                    details={"error": str(error), "resumable": True}))
    await db.commit()


async def _persist(db: AsyncSession, db_run: WorkflowRun, student: Student, actor: User,
                   final_state: Dict[str, Any]) -> bool:
    """Store the assembled draft and set the run's status. Returns whether validation passed."""
    inputs = final_state.get("run_inputs") or {}
    handles = final_state.get("platform_handles") or {}
    resume_data = final_state.get("resume_data") or {}

    perfection_questions = generate_resume_perfection_questions(
        student_profile=final_state.get("student_profile", {}),
        raw_text=resume_data.get("raw_text"),
    )

    # The assembled draft is what gets reviewed, validated again on edit and published
    draft = final_state.get("draft") or {}
    report = final_state.get("validation_report") or {}
    validation_passed = bool(final_state.get("validation_passed", False))
    coding_summary = (final_state.get("coding_analytics") or {}).get("summary") or {}
    result_snapshot = {
        **draft,
        "validation_report": report,
        "evidence_count": len(final_state.get("evidence_records", [])),
        "resume_perfection": {
            "status": "pending_submission",
            "questions": [q.model_dump() for q in perfection_questions],
            "evaluation": None,
        },
        "metadata": {
            **(draft.get("metadata") or {}),
            "github_username": handles.get("github"),
            "leetcode_handle": handles.get("leetcode"),
            # Real LeetCode count when available; the self-reported number is kept separately
            "coding_solved": coding_summary.get("total_solved", 0),
            "self_reported_coding_solved": inputs.get("coding_solved", 0),
            "cgpa": inputs.get("cgpa"),
            "validation_passed": validation_passed,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    # Only validated drafts enter the officer queue (Lab 11)
    db_run.status = "pending_review" if validation_passed else "validation_failed"
    db_run.current_step = final_state.get("current_step", "completed")
    db_run.result_snapshot = result_snapshot
    db_run.error_message = None
    db_run.completed_at = datetime.now(timezone.utc)
    await db.commit()

    audit_events = final_state.get("audit_events", [])
    if audit_events:
        await log_workflow_events(db=db, workflow_run_id=str(db_run.id), events=audit_events,
                                  actor_id=str(actor.id), actor_type="agent")

    db.add(AuditLog(
        actor_id=student.user_id, actor_type="system", workflow_run_id=db_run.id,
        action="SENT_FOR_REVIEW" if validation_passed else "VALIDATION_FAILED_NOT_QUEUED",
        entity_type="workflow_run", entity_id=db_run.id, correlation_id=uuid.uuid4(),
        details={"validation_passed": validation_passed, "errors_count": len(final_state.get("errors", []))},
    ))
    await db.commit()
    return validation_passed


async def run_pipeline(
    db: AsyncSession,
    *,
    db_run: WorkflowRun,
    student: Student,
    actor: User,
    consents: Dict[str, Dict[str, Any]],
    roles: List[str],
    plan: Dict[str, Any],
    handles: Dict[str, Optional[str]],
    cgpa: Optional[float],
    coding_solved: int,
    resume_data: Dict[str, Any],
) -> bool:
    """Execute the graph for `db_run` and persist the result. Returns whether validation passed."""
    github_username, leetcode_handle = handles.get("github"), handles.get("leetcode")
    academic_ok = is_granted(consents, "academic_records")
    initial_state: Dict[str, Any] = {
        "student_id": str(student.id),
        "run_id": str(db_run.id),
        "consent_validated": False,   # set by the consent node from the Consent table
        "platform_handles": {
            "github": (github_username or "").strip() or None,
            "leetcode": (leetcode_handle or "").strip() or None,
        },
        "student_context": {
            "department": student.department,
            "career_preferences": {k: plan.get(k) for k in ("timeline", "skill_level", "priorities")} if plan else {},
            "academic": {"consented": academic_ok, "cgpa": cgpa if academic_ok else None},
        },
        "request_context": plan or {"target_roles": roles},
        # The temporary upload file is deleted after the request; the text is what a resumed run needs
        "resume_data": {k: v for k, v in resume_data.items() if k != "file_path"} if resume_data.get("raw_text")
        else resume_data,
        "target_roles": roles,
        "run_inputs": {"coding_solved": coding_solved, "cgpa": cgpa},
        "current_step": "init",
        "errors": [],
        "audit_events": [],
        "evidence_records": [],
        "retry_count": 0,
        "max_retries": 3,
        "budget_remaining": 100000,
        "validation_passed": False,
        "approval_status": "pending",
    }

    try:
        hub = DatabaseConnectorHub(asyncio.get_running_loop(), actor_id=str(actor.id))
        final_state = await asyncio.to_thread(_invoke_graph, initial_state, str(db_run.id), hub)
    except Exception as e:
        await _fail(db, db_run, e)
        raise

    return await _persist(db, db_run, student, actor, final_state)


async def resume_pipeline(db: AsyncSession, *, db_run: WorkflowRun, actor: User) -> bool:
    """
    Continue an interrupted run from its last saved step (Lab 6). Steps that
    already completed are not repeated. Refused if nothing was saved, the run
    already finished, or the student has since withdrawn resume consent.
    """
    if db_run.status in ("pending_review", "validation_failed", "approved", "published", "rejected"):
        raise ResumeError(f"This run already finished ({db_run.status}).")
    progress = saved_progress(str(db_run.id))
    if not progress["values"]:
        raise ResumeError("No saved progress for this run — start a new analysis instead.")

    student = (await db.execute(select(Student).where(Student.id == db_run.student_id))).scalar_one()
    consents = consent_status((await db.execute(select(Consent).where(Consent.student_id == student.id))).scalars().all())
    if missing_required(consents):
        raise ResumeError("The student has withdrawn consent to process their resume.")

    resumed_from = progress["next"] or ["(already complete)"]
    db_run.status = "running"
    db_run.error_message = None
    db.add(AuditLog(actor_id=actor.id, actor_type=actor.role, workflow_run_id=db_run.id, action="RUN_RESUMED",
                    entity_type="workflow_run", entity_id=db_run.id, correlation_id=uuid.uuid4(),
                    details={"resumed_from": resumed_from,
                             "completed_step": progress["values"].get("current_step")}))
    await db.commit()

    if progress["next"]:
        try:
            hub = DatabaseConnectorHub(asyncio.get_running_loop(), actor_id=str(actor.id))
            await asyncio.to_thread(_invoke_graph, None, str(db_run.id), hub)
        except Exception as e:
            await _fail(db, db_run, e)
            raise
    final_state = saved_progress(str(db_run.id))["values"]
    return await _persist(db, db_run, student, actor, final_state)


async def resume_interrupted_runs() -> List[Dict[str, Any]]:
    """
    On server start: runs left 'running' were cut off by a crash or restart.
    Continue each from its checkpoint; mark the ones with nothing saved as failed.
    """
    from app import database
    outcomes: List[Dict[str, Any]] = []
    async with database.async_session_factory() as db:
        runs = (await db.execute(select(WorkflowRun).where(WorkflowRun.status == "running"))).scalars().all()
        for run in runs:
            actor = (await db.execute(select(User).where(User.id == run.initiated_by))).scalar_one_or_none()
            try:
                if actor is None:
                    raise ResumeError("The user who started this run no longer exists.")
                passed = await resume_pipeline(db, db_run=run, actor=actor)
                outcomes.append({"run_id": str(run.id), "status": run.status, "validation_passed": passed})
            except Exception as exc:
                if run.status == "running":
                    await _fail(db, run, exc)
                outcomes.append({"run_id": str(run.id), "status": "failed", "error": str(exc)})
    return outcomes
