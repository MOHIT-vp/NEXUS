"""Governed connector for student profile and consent data."""
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.connectors.base import BaseConnector, DataAccessDeniedError
from app.models.profile import StudentProfile
from app.models.user import Consent
from app.services.consent import consent_status


class StudentConnector(BaseConnector):
    """Governs read access to a student's records and enforces consent boundaries."""

    async def get_consent_status(self, student_id: uuid.UUID) -> Dict[str, Dict[str, Any]]:
        """Per-source consent read from the Consent table."""
        result = await self.safe_execute(select(Consent).where(Consent.student_id == student_id))
        return consent_status(result.scalars().all())

    async def verify_consent(self, student_id: uuid.UUID, consent_type: str) -> bool:
        return (await self.get_consent_status(student_id)).get(consent_type, {}).get("status") == "granted"

    async def get_student_profile(self, student_id: uuid.UUID) -> Optional[dict]:
        """Fetch a student's parsed profile (requires resume_processing consent)."""
        if not await self.verify_consent(student_id, "resume_processing"):
            raise DataAccessDeniedError("Student has not consented to resume processing.")
        result = await self.safe_execute(
            select(StudentProfile)
            .where(StudentProfile.student_id == student_id)
            .order_by(StudentProfile.created_at.desc())
            .options(selectinload(StudentProfile.skills), selectinload(StudentProfile.projects))
        )
        profile = result.scalars().first()
        if not profile:
            return None
        return {
            "id": str(profile.id),
            "summary": profile.summary,
            "skills": [{"name": s.skill.name if s.skill else "unknown", "proficiency": s.proficiency} for s in profile.skills],
            "projects": [{"title": p.title, "technologies": p.technologies} for p in profile.projects],
        }
