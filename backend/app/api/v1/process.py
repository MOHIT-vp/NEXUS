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
from app.database import get_db
from app.models.user import User, Student
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


class ResumePerfectionSubmitRequest(BaseModel):
    answers: List[StudentAnswerItem]


class ResumePerfectionResponse(BaseModel):
    run_id: str
    status: str
    questions: List[Dict[str, Any]]
    evaluation: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Helpers (MVP Auth Bypass)
# 
# SECURITY WARNING: These helpers generate mock users to bypass authentication
# for the MVP demo. 
# FUTURE REQUIREMENT: Remove these in Phase 3 and use `get_current_student`
# and `get_current_user` dependencies from `deps.py`.
# ---------------------------------------------------------------------------

async def get_or_create_demo_student(db: AsyncSession) -> Student:
    """Fetch or create a demo student for the MVP upload flow."""
    demo_email = "student@demo.com"
    result = await db.execute(select(User).where(User.email == demo_email))
    user = result.scalar_one_or_none()

    if not user:
        from app.services.auth import create_user
        user = await create_user(
            db=db,
            email=demo_email,
            password="password123",
            full_name="Demo Student",
            role="student",
        )

    result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = result.scalar_one_or_none()

    if not student:
        student = Student(user_id=user.id)
        db.add(student)
        await db.flush()

    return student


async def get_or_create_demo_officer(db: AsyncSession) -> User:
    """Fetch or create a demo placement officer for the MVP flow."""
    officer_email = "officer@demo.com"
    result = await db.execute(select(User).where(User.email == officer_email))
    user = result.scalar_one_or_none()

    if not user:
        from app.services.auth import create_user
        user = await create_user(
            db=db,
            email=officer_email,
            password="password123",
            full_name="Demo Officer",
            role="placement_officer",
        )

    return user


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

    # Save to temp file for Resume Agent to read
    suffix = ".pdf" if "pdf" in file.content_type else ".docx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)

    try:
        tmp.write(contents)
        tmp.flush()
        tmp.close()

        # 1. Get or Create Demo Student
        student = await get_or_create_demo_student(db)

        # 2. Create WorkflowRun in DB
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
                    f"detected with an existing resume from another student ({verification.matched_student_name or 'registered student'})."
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

        # 4. Build state and invoke the full LangGraph pipeline
        initial_state: Dict[str, Any] = {
            "student_id": str(student.id),
            "run_id": str(db_run.id),
            "consent_validated": True,
            "resume_data": {
                "file_path": tmp.name,
                "mime_type": file.content_type,
                "raw_text": raw_text,
                "is_duplicate": False,
                "similarity_score": verification.similarity_score,
                "matched_student_id": str(verification.matched_student_id) if verification.matched_student_id else None,
            },
            "target_roles": ["software_engineer", "data_engineer"],
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

        config = {"configurable": {"thread_id": str(db_run.id)}}

        try:
            final_state = agent_runner.invoke(initial_state, config=config)
        except Exception as e:
            db_run.status = "failed"
            db_run.error_message = str(e)
            db_run.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Audit the failure
            fail_audit = AuditLog(
                actor_type="system",
                workflow_run_id=db_run.id,
                action="PIPELINE_FAILED",
                entity_type="workflow_run",
                entity_id=db_run.id,
                correlation_id=uuid.uuid4(),
                details={"error": str(e)},
            )
            db.add(fail_audit)
            await db.commit()

            raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {str(e)}")

        # 5. Build the result snapshot from final state
        # Generate Resume Perfection verification questions based on extracted profile
        perfection_questions = generate_resume_perfection_questions(
            student_profile=final_state.get("student_profile", {}),
            raw_text=raw_text,
        )

        result_snapshot = {
            "student_profile": final_state.get("student_profile", {}),
            "skill_gap_report": final_state.get("skill_gap_report", {}),
            "coding_analytics": final_state.get("coding_analytics", {}),
            "matching_result": final_state.get("matching_result", {}),
            "interview_result": final_state.get("interview_result", {}),
            "roadmap": final_state.get("roadmap", {}),
            "validation_report": final_state.get("validation_report", {}),
            "evidence_count": len(final_state.get("evidence_records", [])),
            "resume_perfection": {
                "status": "pending_submission",
                "questions": [q.model_dump() for q in perfection_questions],
                "evaluation": None,
            },
            "metadata": {
                "github_username": github_username,
                "leetcode_handle": leetcode_handle,
                "coding_solved": coding_solved,
                "cgpa": cgpa,
                "validation_passed": final_state.get("validation_passed", False),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        # 6. Persist to DB — status is PENDING_REVIEW (requires officer approval)
        db_run.status = "pending_review"
        db_run.current_step = final_state.get("current_step", "completed")
        db_run.result_snapshot = result_snapshot
        db_run.completed_at = datetime.now(timezone.utc)
        await db.commit()

        # 7. Write LangGraph audit events to the audit_logs table
        audit_events = final_state.get("audit_events", [])
        if audit_events:
            await log_workflow_events(
                db=db,
                workflow_run_id=str(db_run.id),
                events=audit_events,
                actor_id=str(student.user_id),
                actor_type="agent",
            )

        # 8. Write completion audit log
        completion_audit = AuditLog(
            actor_id=student.user_id,
            actor_type="system",
            workflow_run_id=db_run.id,
            action="SENT_FOR_REVIEW",
            entity_type="workflow_run",
            entity_id=db_run.id,
            correlation_id=uuid.uuid4(),
            details={
                "validation_passed": final_state.get("validation_passed", False),
                "errors_count": len(final_state.get("errors", [])),
            },
        )
        db.add(completion_audit)
        await db.commit()

        return UploadResponse(
            run_id=str(db_run.id),
            status="pending_review",
            message="Your profile has been analyzed and is awaiting Placement Officer review.",
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
    db: AsyncSession = Depends(get_db),
):
    """Returns the current status of a workflow run for frontend polling."""
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id format.")

    result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_uuid))
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found.")

    return StatusResponse(
        run_id=str(run.id),
        status=run.status,
        current_step=run.current_step,
        student_id=str(run.student_id) if run.student_id else None,
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

    result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_uuid))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found.")

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

    result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_uuid))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found.")

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
    db: AsyncSession = Depends(get_db),
):
    """Regenerates a fresh set of questions based on resume content."""
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id format.")

    result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_uuid))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found.")

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
