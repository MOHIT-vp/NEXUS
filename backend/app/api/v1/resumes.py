"""API router for resume uploading, verification, and parsing."""
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_student, get_current_user, get_db
from app.models.user import Student, User
from app.models.profile import Resume, StudentProfile
from app.services.file_storage import save_upload_file
from app.agents.graph import agent_runner
from app.agents.state import PlacementState
from app.agents.tools.resume_tools import extract_text_from_file
from app.services.resume_validator import (
    verify_resume_uniqueness,
    ResumeVerificationResult,
)

router = APIRouter(prefix="/resumes", tags=["Resumes"])


class ResumeUploadResponse(BaseModel):
    resume_id: uuid.UUID
    status: str
    message: str
    similarity_score: Optional[float] = None
    verification_status: Optional[str] = None


class ResumeDetailResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    file_name: str
    file_size: int
    mime_type: str
    file_hash: Optional[str] = None
    status: str
    uploaded_at: Optional[datetime] = None
    parsed_at: Optional[datetime] = None


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a resume, securely store it, verify uniqueness against existing resumes
    from other students (detecting cloned/plagiarized resumes even if only the name changed),
    and dispatch the LangGraph Resume Agent.
    """
    if file.content_type not in ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and DOCX files are allowed."
        )

    # 1. Read & Securely Store
    contents = await file.read()
    try:
        file_path, file_hash, file_size = await save_upload_file(
            file_content=contents,
            original_filename=file.filename,
            content_type=file.content_type
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 1.5 Extract Mechanical Text
    try:
        raw_text = extract_text_from_file(file_path, file.content_type)
    except Exception as e:
        raw_text = ""

    # 2. Database Record
    db_resume = Resume(
        id=uuid.uuid4(),
        student_id=student.id,
        file_name=file.filename,
        file_path=file_path,
        file_size=file_size,
        mime_type=file.content_type,
        file_hash=file_hash,
        raw_text=raw_text,
        status="uploaded"
    )
    db.add(db_resume)
    await db.commit()
    await db.refresh(db_resume)

    # 2.5 Resume Verification (Duplicate / Plagiarism Detection Strategy)
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
        current_resume_id=db_resume.id,
    )

    if verification.is_duplicate:
        db_resume.status = "rejected_duplicate"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "DUPLICATE_RESUME_DETECTED",
                "message": (
                    f"Resume validation failed: High similarity ({verification.similarity_score * 100:.1f}%) "
                    f"detected with an existing resume from another student."
                ),
                "similarity_score": verification.similarity_score,
                "matched_resume_id": str(verification.matched_resume_id) if verification.matched_resume_id else None,
                "matched_student_id": str(verification.matched_student_id) if verification.matched_student_id else None,
                "matched_student_name": verification.matched_student_name,
                "reasons": verification.reasons,
                "metrics": verification.metrics,
            }
        )

    db_resume.status = "processing"
    await db.commit()

    # 3. Trigger Resume Agent directly (Since we are testing the agent in Lab 2)
    # Normally this is triggered by the coordinator via /workflows/start.
    initial_state = {
        "student_id": str(student.id),
        "run_id": str(uuid.uuid4()),
        "consent_validated": True, # Hardcoded for Lab 2 isolation testing
        "resume_data": {
            "file_path": file_path,
            "mime_type": file.content_type,
            "raw_text": raw_text,
            "is_duplicate": False,
            "similarity_score": verification.similarity_score,
            "matched_student_id": str(verification.matched_student_id) if verification.matched_student_id else None,
        },
        "current_step": "init",
    }
    
    # We invoke the subgraph directly for immediate feedback in this lab
    thread = {"configurable": {"thread_id": str(db_resume.id)}}
    try:
         # In a real scenario we'd use Celery for async execution, but we'll wait for it here
         final_state = agent_runner.invoke(initial_state, config=thread)
    except Exception as e:
        db_resume.status = "failed"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"LLM Processing failed: {str(e)}")

    if "errors" in final_state and final_state["errors"]:
        db_resume.status = "failed"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Agent Error: {final_state['errors']}")

    # 4. Save extracted profile
    profile_data = final_state.get("student_profile", {})
    if profile_data:
        db_resume.status = "parsed"
        
        # Upsert Student Profile
        db_profile = StudentProfile(
            student_id=student.id,
            resume_id=db_resume.id,
            summary=profile_data.get("summary", ""),
            status="draft"
        )
        db.add(db_profile)
        # In a full implementation, we'd iterate and save the skills/projects DB models as well!
        
        await db.commit()
        
    return {
        "resume_id": db_resume.id,
        "status": "success",
        "message": "Resume uploaded and successfully parsed by the Agent.",
        "similarity_score": verification.similarity_score,
        "verification_status": verification.status,
    }


@router.post("/{resume_id}/verify", response_model=ResumeVerificationResult)
async def verify_resume_endpoint(
    resume_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    On-demand verification of an existing uploaded resume against the corpus of other students.
    """
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    if resume.student_id != student.id:
        raise HTTPException(status_code=403, detail="Access denied: not your resume")

    raw_text = resume.raw_text
    if not raw_text and resume.file_path:
        try:
            raw_text = extract_text_from_file(resume.file_path, resume.mime_type)
            resume.raw_text = raw_text
            db.add(resume)
            await db.commit()
        except Exception:
            raw_text = ""

    student_name = None
    if "user" in student.__dict__ and student.user:
        student_name = getattr(student.user, "full_name", None)
    elif getattr(student, "user_id", None):
        user_res = await db.execute(select(User.full_name).where(User.id == student.user_id))
        student_name = user_res.scalar_one_or_none()

    verification = await verify_resume_uniqueness(
        db=db,
        current_student_id=student.id,
        raw_text=raw_text or "",
        file_hash=resume.file_hash,
        current_student_name=student_name,
        current_resume_id=resume.id,
    )
    return verification


@router.get("", response_model=List[ResumeDetailResponse])
async def list_student_resumes(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """List all resumes uploaded by the current student."""
    result = await db.execute(
        select(Resume).where(Resume.student_id == student.id).order_by(Resume.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{resume_id}", response_model=ResumeDetailResponse)
async def get_resume_detail(
    resume_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Get single resume metadata and status."""
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if resume.student_id != student.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return resume

