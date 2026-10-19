"""SQLAlchemy models — Users, Auth, Students, Officers."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    """Core user account for all roles."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(
        String(50),
        nullable=False,
        index=True,
    )
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    student = relationship("Student", back_populates="user", uselist=False)
    placement_officer = relationship("PlacementOfficer", back_populates="user", uselist=False)


class Student(Base):
    """Student-specific profile linked to a user."""
    __tablename__ = "students"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    enrollment_no = Column(String(50), unique=True, nullable=True)
    department = Column(String(100), nullable=True)
    semester = Column(Integer, nullable=True)
    cgpa = Column(Numeric(4, 2), nullable=True)
    phone = Column(String(20), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    github_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    user = relationship("User", back_populates="student")
    consents = relationship("Consent", back_populates="student", cascade="all, delete-orphan")
    resumes = relationship("Resume", back_populates="student", cascade="all, delete-orphan")
    profiles = relationship("StudentProfile", back_populates="student", cascade="all, delete-orphan")
    coding_analytics = relationship("CodingAnalytics", back_populates="student", cascade="all, delete-orphan")
    skill_gap_reports = relationship("SkillGapReport", back_populates="student", cascade="all, delete-orphan")
    readiness_scores = relationship("ReadinessScore", back_populates="student", cascade="all, delete-orphan")
    company_matches = relationship("CompanyMatch", back_populates="student", cascade="all, delete-orphan")
    interview_sessions = relationship("InterviewSession", back_populates="student", cascade="all, delete-orphan")
    roadmaps = relationship("Roadmap", back_populates="student", cascade="all, delete-orphan")
    workflow_runs = relationship("WorkflowRun", back_populates="student", cascade="all, delete-orphan")
    versions = relationship("Version", back_populates="student", cascade="all, delete-orphan")


class PlacementOfficer(Base):
    """Placement officer profile."""
    __tablename__ = "placement_officers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    department = Column(String(100), nullable=True)
    designation = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="placement_officer")


class Consent(Base):
    """Per-type consent records for students."""
    __tablename__ = "consents"
    __table_args__ = (
        UniqueConstraint("student_id", "consent_type", name="uq_consent_student_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    consent_type = Column(String(50), nullable=False)
    granted = Column(Boolean, nullable=False, default=False)
    granted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    student = relationship("Student", back_populates="consents")


class RevokedToken(Base):
    """Access tokens ended by sign-out; checked on every authenticated request."""
    __tablename__ = "revoked_tokens"

    jti = Column(String(64), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), default=utcnow)
