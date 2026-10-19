"""
Mock interview API — timed practice rounds for students (aptitude, verbal,
CS fundamentals, coding, spoken English, essay). Attempts are recorded in the
audit log (score only — answers are not stored) and listed as history.
"""
import asyncio
import hashlib
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_student, get_db
from app.models.user import Student
from app.models.workflow import AuditLog
from app.services import mock_interview as svc

router = APIRouter(prefix="/mock", tags=["Mock Interview"])


class StartRequest(BaseModel):
    section: str
    count: int = Field(..., ge=1, le=50)
    minutes: int = Field(..., ge=1, le=svc.MAX_MINUTES)
    subjects: Optional[List[str]] = None


class SubmitRequest(BaseModel):
    session_token: str
    answers: Dict[str, Any] = Field(default_factory=dict)
    durations: Optional[Dict[str, float]] = None   # seconds spoken per question (spoken English)


@router.get("/sections")
async def sections(_student: Student = Depends(get_current_student)):
    return svc.list_sections()


@router.post("/start")
async def start(body: StartRequest, student: Student = Depends(get_current_student)):
    try:
        return svc.start_session(str(student.user_id), body.section, body.count, body.minutes, body.subjects)
    except svc.MockError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/submit")
async def submit(body: SubmitRequest, student: Student = Depends(get_current_student), db: AsyncSession = Depends(get_db)):
    session_id = hashlib.sha256(body.session_token.encode()).hexdigest()[:32]
    used = (await db.execute(select(AuditLog.id).where(
        AuditLog.actor_id == student.user_id, AuditLog.action == "MOCK_SECTION_COMPLETED",
        AuditLog.details["session"].astext == session_id))).first()
    if used:
        raise HTTPException(status_code=409, detail="This test was already submitted. Start a new one to try again.")
    try:
        # Coding answers run in a sandboxed subprocess — keep the event loop free
        result = await asyncio.to_thread(svc.grade_session, str(student.user_id), body.session_token, body.answers, body.durations)
    except svc.MockError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.add(AuditLog(actor_id=student.user_id, actor_type="student", agent_name="InterviewAgent",
                    action="MOCK_SECTION_COMPLETED", entity_type="student", entity_id=student.id,
                    correlation_id=uuid.uuid4(),
                    details={"session": session_id, "section": result["section"], "title": result["title"],
                             "score": result["score"], "max_score": result["max_score"], "percentage": result["percentage"],
                             "questions": result["questions"], "time_taken_seconds": result["time_taken_seconds"],
                             "submitted_late": result["submitted_late"]}))
    await db.commit()
    return result


@router.get("/history")
async def history(limit: int = Query(20, ge=1, le=100), student: Student = Depends(get_current_student),
                  db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(AuditLog).where(
        AuditLog.actor_id == student.user_id, AuditLog.action == "MOCK_SECTION_COMPLETED",
    ).order_by(AuditLog.timestamp.desc()).limit(limit))).scalars().all()
    return [{"at": r.timestamp.isoformat() if r.timestamp else None, **{k: v for k, v in (r.details or {}).items() if k != "session"}}
            for r in rows]
