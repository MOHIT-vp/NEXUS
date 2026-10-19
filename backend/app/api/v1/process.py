"""
Process API endpoint — Real LangGraph pipeline with full persistence.

Accepts a resume file upload, creates/fetches a demo student,
starts the workflow run, invokes the full LangGraph pipeline,
persists the result snapshot to PostgreSQL, writes audit logs,
and returns a run_id for the frontend to poll.

The result enters PENDING_REVIEW status and requires officer approval
before becoming visible on the student dashboard.
"""
import os
import uuid
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

import hashlib
import asyncio
import json


from app.services.pipeline import run_pipeline
from app.api.deps import can_view_run, get_current_student, get_current_user
from app.database import get_db
from app.models.user import Consent, User, Student
from app.services.consent import consent_status, is_granted, missing_required
from app.models.profile import Resume
from app.models.workflow import WorkflowRun, AuditLog, Version
from app.agents.graph import agent_runner
from app.agents.tools.resume_tools import extract_text_from_file
from app.services.resume_validator import verify_resume_uniqueness
from app.services.audit import log_workflow_events
from app.services.resume_perfection_service import (
    ResumePerfectionQuestion,
    StudentAnswerItem,
    ResumePerfectionEvaluation,
    generate_resume_perfection_questions,
    evaluate_student_answers,
    sanitize_question_for_client,
)

router = APIRouter(prefix="/process", tags=["Process"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    run_id: str
    status: str
    message: str


class StatusResponse(BaseModel):
    run_id: str
    status: str
    current_step: Optional[str] = None
    student_id: Optional[str] = None
    validation_failures: List[Dict[str, Any]] = []


class ResumePerfectionSubmitRequest(BaseModel):
    answers: List[StudentAnswerItem]


class ResumePerfectionResponse(BaseModel):
    run_id: str
    status: str
    questions: List[Dict[str, Any]]
    evaluation: Optional[Dict[str, Any]] = None


async def _own_run(db: AsyncSession, run_uuid: uuid.UUID, user: User) -> WorkflowRun:
    run = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_uuid))).scalar_one_or_none()
    if not run or not await can_view_run(db, user, run):
        raise HTTPException(status_code=404, detail="Workflow run not found.")
    return run


# ---------------------------------------------------------------------------
# Upload + Pipeline Execution
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=UploadResponse, summary="Upload resume and start real LangGraph pipeline")
async def process_resume(
    file: UploadFile = File(...),
    github_username: Optional[str] = Form(None),
    leetcode_handle: Optional[str] = Form(None),
    coding_solved: int = Form(0),
    cgpa: Optional[float] = Form(None),
    target_roles: Optional[str] = Form(None),      # JSON list or comma-separated, from the planner
    career_plan: Optional[str] = Form(None),       # JSON plan returned by /planner/clarify
    user: User = Depends(get_current_user),
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    Accepts a resume file, invokes the full LangGraph pipeline,
    persists the result to PostgreSQL, and returns a run_id.

    The result enters PENDING_REVIEW status. The officer must approve
    before the student can see the final dashboard.
    """
    # Validate file type
    allowed_types = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only PDF or DOCX files accepted.")

    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 5 MB limit.")

    # Explicit per-source consent, read from the Consent table (never assumed)
    consents = consent_status((await db.execute(select(Consent).where(Consent.student_id == student.id))).scalars().all())
    missing = missing_required(consents)
    if missing:
        raise HTTPException(status_code=409, detail="Consent to analyse your resume is required before upload.")

    # Target roles come from the student (career planner); there is no default role
    roles: List[str] = []
    if target_roles:
        try:
            parsed = json.loads(target_roles)
            roles = [str(r) for r in parsed] if isinstance(parsed, list) else [str(parsed)]
        except ValueError:
            roles = [r.strip() for r in target_roles.split(",")]
    roles = [r for r in roles if r.strip()]
    if not roles:
        raise HTTPException(status_code=409, detail="Tell us your target role first (career goal step).")
    plan: Dict[str, Any] = {}
    if career_plan:
        try:
            plan = json.loads(career_plan) or {}
        except ValueError:
            plan = {}

    # Handles and CGPA are saved on the student's own record
    if github_username is not None:
        student.github_url = f"https://github.com/{github_username.strip()}" if github_username.strip() else None
    if cgpa is not None:
        student.cgpa = cgpa

    # Save to temp file for Resume Agent to read
    suffix = ".pdf" if "pdf" in file.content_type else ".docx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)

    try:
        tmp.write(contents)
        tmp.flush()
        tmp.close()

        # 2. Create WorkflowRun in DB (owned by the authenticated student)
        db_run = WorkflowRun(
            student_id=student.id,
            initiated_by=student.user_id,
            status="running",
            current_step="init",
            started_at=datetime.now(timezone.utc),
        )
        db.add(db_run)
        await db.commit()
        await db.refresh(db_run)

        # 3. Write initial audit log
        init_audit = AuditLog(
            actor_id=student.user_id,
            actor_type="student",
            workflow_run_id=db_run.id,
            action="RUN_CREATED",
            entity_type="workflow_run",
            entity_id=db_run.id,
            correlation_id=uuid.uuid4(),
            details={
                "github_username": github_username,
                "leetcode_handle": leetcode_handle,
                "coding_solved": coding_solved,
                "cgpa": cgpa,
                "file_name": file.filename,
            },
        )
        db.add(init_audit)
        await db.commit()

        # Extract text & compute hash for resume uniqueness validation
        try:
            raw_text = extract_text_from_file(tmp.name, file.content_type)
        except Exception:
            raw_text = ""
        file_hash = hashlib.sha256(contents).hexdigest()

        # Validate resume uniqueness (catch cross-student clones even with changed names)
        student_name = None
        if "user" in student.__dict__ and student.user:
            student_name = getattr(student.user, "full_name", None)
        elif getattr(student, "user_id", None):
            user_res = await db.execute(select(User.full_name).where(User.id == student.user_id))
            student_name = user_res.scalar_one_or_none()

        verification = await verify_resume_uniqueness(
            db=db,
            current_student_id=student.id,
            raw_text=raw_text,
            file_hash=file_hash,
            current_student_name=student_name,
        )

        if verification.is_duplicate:
            db_run.status = "failed"
            db_run.error_message = (
                f"Resume validation failed: High similarity ({verification.similarity_score * 100:.1f}%) "
                f"detected with an existing resume from another student."
            )
            db_run.completed_at = datetime.now(timezone.utc)
            reject_audit = AuditLog(
                actor_id=student.user_id,
                actor_type="student",
                workflow_run_id=db_run.id,
                action="RESUME_REJECTED_DUPLICATE",
                entity_type="workflow_run",
                entity_id=db_run.id,
                correlation_id=uuid.uuid4(),
                details={
                    "similarity_score": verification.similarity_score,
                    "matched_student_id": str(verification.matched_student_id) if verification.matched_student_id else None,
                    "matched_student_name": verification.matched_student_name,
                    "reasons": verification.reasons,
                },
            )
            db.add(reject_audit)
            await db.commit()
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Resume validation failed: High similarity ({verification.similarity_score * 100:.1f}%) "
                    f"detected with an existing resume from another student."
                ),
            )

        # Register verified resume in DB
        db_resume = Resume(
            id=uuid.uuid4(),
            student_id=student.id,
            file_name=file.filename,
            file_path=tmp.name,
            file_size=len(contents),
            mime_type=file.content_type,
            file_hash=file_hash,
            raw_text=raw_text,
            status="verified",
        )
        db.add(db_resume)
        await db.commit()

        # 4–8. Run the agent pipeline and store the validated draft
        validation_passed = await run_pipeline(
            db, db_run=db_run, student=student, actor=user, consents=consents, roles=roles, plan=plan,
            handles={"github": github_username, "leetcode": leetcode_handle}, cgpa=cgpa, coding_solved=coding_solved,
            resume_data={
                "file_path": tmp.name,
                "file_name": file.filename,
                "mime_type": file.content_type,
                "raw_text": raw_text,
                "is_duplicate": False,
                "similarity_score": verification.similarity_score,
                "matched_student_id": str(verification.matched_student_id) if verification.matched_student_id else None,
            },
        )

        return UploadResponse(
            run_id=str(db_run.id),
            status=db_run.status,
            message=("Your profile has been analyzed and is awaiting Placement Officer review."
                     if validation_passed else
                     "Your analysis did not pass the required checks, so it was not sent for review."),
        )

    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)


# ---------------------------------------------------------------------------
# Status Polling
# ---------------------------------------------------------------------------

@router.get("/status/{run_id}", response_model=StatusResponse, summary="Poll workflow status")
async def get_workflow_status(
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Status of the caller's own run (or any run, for the Placement Cell), with validation failures."""
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id format.")
    run = await _own_run(db, run_uuid, user)
    failures = []
    if run.status == "validation_failed":
        report = (run.result_snapshot or {}).get("validation_report") or {}
        failures = [{"code": c["code"], "name": c["name"], "message": c["message"]}
                    for c in report.get("checks", []) if not c.get("passed") and c.get("severity") == "error"]
    return StatusResponse(
        run_id=str(run.id),
        status=run.status,
        current_step=run.current_step,
        student_id=str(run.student_id) if run.student_id else None,
        validation_failures=failures,
    )


# ---------------------------------------------------------------------------
# Resume Perfection & Authenticity Verification Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/runs/{run_id}/resume-perfection",
    response_model=ResumePerfectionResponse,
    summary="Get resume perfection questions & current evaluation",
)
async def get_resume_perfection(
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns targeted questions generated from the uploaded resume to evaluate
    the student's perfection with their own claims. Also returns the evaluation
    result if already completed.
    """
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id format.")

    run = await _own_run(db, run_uuid, user)

    snapshot = run.result_snapshot or {}
    perf_data = snapshot.get("resume_perfection")

    if not perf_data or not perf_data.get("questions"):
        student_profile = snapshot.get("student_profile", {})
        raw_text = snapshot.get("metadata", {}).get("raw_text")
        questions = generate_resume_perfection_questions(student_profile, raw_text)
        perf_data = {
            "status": "pending_submission",
            "questions": [q.model_dump() for q in questions],
            "evaluation": None,
        }
        snapshot["resume_perfection"] = perf_data
        run.result_snapshot = dict(snapshot)
        flag_modified(run, "result_snapshot")
        await db.commit()

    is_evaluated = perf_data.get("status") == "evaluated"
    client_questions = [
        sanitize_question_for_client(q, is_evaluated=is_evaluated)
        for q in perf_data.get("questions", [])
    ]

    return ResumePerfectionResponse(
        run_id=str(run.id),
        status=perf_data.get("status", "pending_submission"),
        questions=client_questions,
        evaluation=perf_data.get("evaluation"),
    )


@router.post(
    "/runs/{run_id}/resume-perfection/submit",
    summary="Submit student answers to evaluate resume perfection",
)
async def submit_resume_perfection_answers(
    run_id: str,
    payload: ResumePerfectionSubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submits student responses to resume verification questions, computes
    the perfection score, generates targeted feedback, and persists results.
    """
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id format.")

    run = await _own_run(db, run_uuid, user)

    snapshot = run.result_snapshot or {}
    perf_data = snapshot.get("resume_perfection") or {}
    raw_questions = perf_data.get("questions") or []

    if not raw_questions:
        student_profile = snapshot.get("student_profile", {})
        questions_objs = generate_resume_perfection_questions(student_profile)
        raw_questions = [q.model_dump() for q in questions_objs]

    # Reconstruct question models
    questions = [ResumePerfectionQuestion(**q) for q in raw_questions]

    # Evaluate answers
    evaluation = evaluate_student_answers(questions, payload.answers)

    # Persist in run result_snapshot
    perf_data["status"] = "evaluated"
    perf_data["questions"] = raw_questions
    perf_data["evaluation"] = evaluation.model_dump()
    snapshot["resume_perfection"] = perf_data
    run.result_snapshot = dict(snapshot)
    flag_modified(run, "result_snapshot")

    # If published versions exist for this run, sync them
    version_result = await db.execute(
        select(Version).where(Version.workflow_run_id == run_uuid)
    )
    versions = version_result.scalars().all()
    for v in versions:
        v_snap = v.snapshot or {}
        v_snap["resume_perfection"] = perf_data
        v.snapshot = dict(v_snap)
        flag_modified(v, "snapshot")

    # Add audit log
    audit = AuditLog(
        actor_id=run.initiated_by,
        actor_type="student",
        workflow_run_id=run.id,
        action="RESUME_PERFECTION_EVALUATED",
        entity_type="workflow_run",
        entity_id=run.id,
        correlation_id=uuid.uuid4(),
        details={
            "score": evaluation.overall_score,
            "tier": evaluation.perfection_tier,
            "total_questions": evaluation.total_questions,
            "correct_count": evaluation.correct_count,
        },
    )
    db.add(audit)
    await db.commit()

    return {
        "run_id": str(run.id),
        "status": "evaluated",
        "evaluation": evaluation.model_dump(),
    }


@router.post(
    "/runs/{run_id}/resume-perfection/regenerate",
    summary="Regenerate resume perfection questions",
)
async def regenerate_resume_perfection(
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Regenerates a fresh set of questions based on resume content."""
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id format.")

    run = await _own_run(db, run_uuid, user)

    snapshot = run.result_snapshot or {}
    student_profile = snapshot.get("student_profile", {})
    raw_text = snapshot.get("metadata", {}).get("raw_text")

    fresh_salt = uuid.uuid4().hex[:6]
    questions = generate_resume_perfection_questions(student_profile, raw_text, seed_salt=fresh_salt)
    raw_questions = [q.model_dump() for q in questions]
    perf_data = {
        "status": "pending_submission",
        "questions": raw_questions,
        "evaluation": None,
    }
    snapshot["resume_perfection"] = perf_data
    run.result_snapshot = dict(snapshot)
    flag_modified(run, "result_snapshot")
    await db.commit()

    client_questions = [
        sanitize_question_for_client(q, is_evaluated=False)
        for q in raw_questions
    ]

    return {
        "run_id": str(run.id),
        "status": "pending_submission",
        "questions": client_questions,
    }
