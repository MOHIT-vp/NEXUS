"""SQLAlchemy models — Analytics, Gaps, Scores, Matches, Interview, Roadmap."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, Numeric,
    String, Text,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class CodingAnalytics(Base):
    """Aggregated coding platform data."""
    __tablename__ = "coding_analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(String(50), nullable=False)
    total_solved = Column(Integer, default=0)
    easy_solved = Column(Integer, default=0)
    medium_solved = Column(Integer, default=0)
    hard_solved = Column(Integer, default=0)
    contest_rating = Column(Integer, nullable=True)
    contests_participated = Column(Integer, default=0)
    best_contest_rank = Column(Integer, nullable=True)
    streak_days = Column(Integer, default=0)
    active_days = Column(Integer, default=0)
    topic_stats = Column(JSONB, nullable=True)
    handle = Column(String(100), nullable=True)
    # ok | not_found | rate_limited | unavailable
    fetch_status = Column(String(30), nullable=True)
    source_url = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    profile_data = Column(JSONB, nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    student = relationship("Student", back_populates="coding_analytics")


class SkillGapReport(Base):
    """Skill gap analysis report for a student vs target role."""
    __tablename__ = "skill_gap_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"), nullable=False)
    target_role = Column(String(100), nullable=True)
    target_job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True)
    overall_coverage = Column(Numeric(5, 2), nullable=True)
    status = Column(String(50), default="draft")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    student = relationship("Student", back_populates="skill_gap_reports")
    items = relationship("SkillGapItem", back_populates="report", cascade="all, delete-orphan")


class SkillGapItem(Base):
    """Individual skill gap entry."""
    __tablename__ = "skill_gap_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("skill_gap_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False)
    required_level = Column(String(20), nullable=False)
    current_level = Column(String(20), nullable=True)
    gap_severity = Column(String(20), nullable=True)
    is_strength = Column(Boolean, default=False)
    evidence_id = Column(UUID(as_uuid=True), nullable=True)
    recommendation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    report = relationship("SkillGapReport", back_populates="items")
    skill = relationship("Skill")


class ReadinessScore(Base):
    """Computed readiness score for a student."""
    __tablename__ = "readiness_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_run_id = Column(UUID(as_uuid=True), ForeignKey("workflow_runs.id"), nullable=True)
    total_score = Column(Numeric(5, 2), nullable=False)
    max_score = Column(Numeric(5, 2), default=100.0)
    percentile = Column(Numeric(5, 2), nullable=True)
    status = Column(String(50), default="draft")
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    student = relationship("Student", back_populates="readiness_scores")
    breakdowns = relationship("ScoreBreakdown", back_populates="score", cascade="all, delete-orphan")


class ScoreBreakdown(Base):
    """Individual component of a readiness score."""
    __tablename__ = "score_breakdowns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    score_id = Column(UUID(as_uuid=True), ForeignKey("readiness_scores.id", ondelete="CASCADE"), nullable=False, index=True)
    component = Column(String(50), nullable=False)
    points = Column(Numeric(5, 2), nullable=False)
    max_points = Column(Numeric(5, 2), nullable=False)
    weight = Column(Numeric(5, 2), nullable=False)
    weighted_score = Column(Numeric(5, 2), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    score = relationship("ReadinessScore", back_populates="breakdowns")


class CompanyMatch(Base):
    """Ranked company/role match for a student."""
    __tablename__ = "company_matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    score_id = Column(UUID(as_uuid=True), ForeignKey("readiness_scores.id"), nullable=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    match_score = Column(Numeric(5, 2), nullable=False)
    confidence = Column(Numeric(3, 2), nullable=False)
    rank = Column(Integer, nullable=True)
    reasoning = Column(Text, nullable=False)
    is_eligible = Column(Boolean, default=True)
    eligibility_notes = Column(Text, nullable=True)
    is_low_confidence = Column(Boolean, default=False, index=True)
    evidence_id = Column(UUID(as_uuid=True), nullable=True)
    status = Column(String(50), default="draft")
    created_at = Column(DateTime(timezone=True), default=utcnow)

    student = relationship("Student", back_populates="company_matches")
    job = relationship("Job")
    company = relationship("Company")


class InterviewSession(Base):
    """Mock interview session."""
    __tablename__ = "interview_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    target_role = Column(String(100), nullable=True)
    session_type = Column(String(50), nullable=True)
    status = Column(String(50), default="pending")
    overall_score = Column(Numeric(5, 2), nullable=True)
    feedback_summary = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    student = relationship("Student", back_populates="interview_sessions")
    questions = relationship("InterviewQuestion", back_populates="session", cascade="all, delete-orphan")


class InterviewQuestion(Base):
    """Individual interview question."""
    __tablename__ = "interview_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(50), nullable=True)
    difficulty = Column(String(20), nullable=True)
    skill_targeted = Column(UUID(as_uuid=True), ForeignKey("skills.id"), nullable=True)
    sequence_order = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    session = relationship("InterviewSession", back_populates="questions")
    response = relationship("InterviewResponse", back_populates="question", uselist=False)


class InterviewResponse(Base):
    """Student response to an interview question."""
    __tablename__ = "interview_responses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False)
    response_text = Column(Text, nullable=False)
    score = Column(Numeric(5, 2), nullable=True)
    max_score = Column(Numeric(5, 2), default=10.0)
    ai_feedback = Column(Text, nullable=True)
    strengths = Column(ARRAY(Text), nullable=True)
    improvements = Column(ARRAY(Text), nullable=True)
    is_ai_evaluated = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    question = relationship("InterviewQuestion", back_populates="response")


class Roadmap(Base):
    """Learning roadmap for a student."""
    __tablename__ = "roadmaps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=True)
    target_role = Column(String(100), nullable=True)
    total_items = Column(Integer, default=0)
    completed_items = Column(Integer, default=0)
    status = Column(String(50), default="draft")
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    student = relationship("Student", back_populates="roadmaps")
    items = relationship("RoadmapItem", back_populates="roadmap", cascade="all, delete-orphan")


class RoadmapItem(Base):
    """Individual roadmap item/milestone."""
    __tablename__ = "roadmap_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    roadmap_id = Column(UUID(as_uuid=True), ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False)
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String(20), nullable=True)
    category = Column(String(50), nullable=True)
    resources = Column(JSONB, nullable=True)
    estimated_hours = Column(Integer, nullable=True)
    sequence_order = Column(Integer, nullable=True)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    roadmap = relationship("Roadmap", back_populates="items")
