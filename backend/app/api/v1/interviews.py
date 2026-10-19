"""
Lab 13: Domain Specialists — Interviews API.
"""
import uuid
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_student, get_db
from app.models.user import Student
from app.models.workflow import AuditLog, Version
from app.services.mock_practice import evaluate_answer, practice_questions

router = APIRouter(prefix="/interviews", tags=["Interviews"])


async def _published_plan(db: AsyncSession, student: Student):
    return (await db.execute(
        select(Version).where(Version.student_id == student.id, Version.entity_type == "readiness_plan",
                              Version.status == "published").order_by(Version.version_number.desc()).limit(1)
    )).scalar_one_or_none()


@router.get("/me", response_model=Dict[str, Any])
async def get_my_interviews(
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the mock interview results and learning roadmap from the latest approved readiness plan.
    """
    result = await db.execute(
        select(Version)
        .where(
            Version.student_id == current_student.id,
            Version.entity_type == "readiness_plan",
            Version.status == "published"
        )
        .order_by(Version.version_number.desc())
        .limit(1)
    )
    version = result.scalar_one_or_none()

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No approved interview data found."
        )

    return {
        "interview_result": version.snapshot.get("interview_result"),
        "roadmap": version.snapshot.get("roadmap")
    }


class PracticeAnswer(BaseModel):
    question_index: int = Field(..., ge=0)
    answer: str = Field(..., min_length=1, max_length=6000)


@router.get("/practice", response_model=Dict[str, Any])
async def list_practice_questions(
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Mock-interview questions from the student's published plan."""
    version = await _published_plan(db, current_student)
    if not version:
        raise HTTPException(status_code=404, detail="Your plan hasn't been published yet.")
    return {"questions": practice_questions(version.snapshot.get("interview_result") or {})}


@router.post("/practice", response_model=Dict[str, Any])
async def answer_practice_question(
    body: PracticeAnswer,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Answer one practice question and get feedback (AI-generated or rubric-based, always labelled)."""
    version = await _published_plan(db, current_student)
    if not version:
        raise HTTPException(status_code=404, detail="Your plan hasn't been published yet.")
    questions = (version.snapshot.get("interview_result") or {}).get("questions") or []
    if body.question_index >= len(questions):
        raise HTTPException(status_code=404, detail="Question not found.")
    feedback = evaluate_answer(questions[body.question_index], body.answer)
    # The answer text is not stored; only that a practice attempt happened and its score
    db.add(AuditLog(actor_id=current_student.user_id, actor_type="student", agent_name="InterviewAgent",
                    action="MOCK_PRACTICE_ANSWERED", entity_type="version", entity_id=version.id,
                    correlation_id=uuid.uuid4(),
                    details={"question_index": body.question_index, "score": feedback["score"], "method": feedback["method"]}))
    await db.commit()
    return feedback
