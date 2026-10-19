"""
Career planner (Lab 1): clarify → plan → revise.

POST /planner/clarify takes the student's request plus any answers or feedback
given so far and returns either clarifying questions (a vague request always
gets at least two) or a draft plan, which the student can revise with feedback.
The conversation state (`slots`) is returned to the client and sent back on the
next call, so nothing extra is stored until the plan is submitted with the resume.
"""
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_student
from app.models.user import Student
from app.services import planner as P

router = APIRouter(prefix="/planner", tags=["Career Planner"])


class ClarifyRequest(BaseModel):
    request: str = Field(..., min_length=2, max_length=2000)
    slots: Optional[Dict[str, Any]] = None                       # state from the previous response
    answers: Optional[Dict[str, Union[str, List[str]]]] = None   # answers to the questions asked
    feedback: Optional[str] = Field(None, max_length=2000)       # revision request on a draft plan


@router.post("/clarify")
async def clarify(body: ClarifyRequest, student: Student = Depends(get_current_student)):
    if body.slots is None:
        slots, _ = P.analyze_request(body.request)
    else:
        slots = dict(body.slots)

    errors: Dict[str, str] = {}
    for qid, ans in (body.answers or {}).items():
        err = P.apply_answer(slots, qid, ans)
        if err:
            errors[qid] = err

    changes: List[str] = []
    if body.feedback and body.feedback.strip():
        if P.missing_slots(slots):
            raise HTTPException(status_code=409, detail="Answer the questions before revising the plan.")
        slots, changes = P.revise_plan(slots, body.feedback)

    missing = P.missing_slots(slots)
    if missing:
        return {"status": "needs_clarification", "questions": P.questions_for(missing), "slots": slots,
                "answer_errors": errors}
    return {"status": "draft_ready", "questions": [], "slots": slots, "plan": P.build_plan(slots),
            "changes": changes, "answer_errors": errors,
            "message": None if changes or not body.feedback else "No changes recognised in your feedback."}
