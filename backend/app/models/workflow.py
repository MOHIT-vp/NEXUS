"""SQLAlchemy models — Workflow, Validation, Approval, Evidence, Audit, Versioning."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Computed, DateTime, ForeignKey, Index, Integer, Numeric,
    String, Text,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class WorkflowRun(Base):
    """A single execution of the placement readiness pipeline."""
    __tablename__ = "workflow_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    initiated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(String(50), default="pending", index=True)
    execution_plan = Column(JSONB, nullable=True)
    current_step = Column(String(100), nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    error_message = Column(Text, nullable=True)
    result_snapshot = Column(JSONB, nullable=True)  # Full agent outputs after pipeline completion
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    student = relationship("Student", back_populates="workflow_runs")
    agent_executions = relationship("AgentExecution", back_populates="workflow_run", cascade="all, delete-orphan")
    validation_reports = relationship("ValidationReport", back_populates="workflow_run", cascade="all, delete-orphan")
    approval_decisions = relationship("ApprovalDecision", back_populates="workflow_run", cascade="all, delete-orphan")


class AgentExecution(Base):
    """Record of a single agent's execution within a workflow."""
    __tablename__ = "agent_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_run_id = Column(UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False, index=True)
    status = Column(String(50), default="pending")
    input_data = Column(JSONB, nullable=True)
    output_data = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    token_usage = Column(JSONB, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    workflow_run = relationship("WorkflowRun", back_populates="agent_executions")


class ValidationReport(Base):
    """Validation report for a workflow run."""
    __tablename__ = "validation_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_run_id = Column(UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    passed = Column(Boolean, nullable=False)
    total_checks = Column(Integer, nullable=False)
    passed_checks = Column(Integer, nullable=False)
    failed_checks = Column(Integer, nullable=False)
    diagnosis = Column(Text, nullable=True)
    attempt_number = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    workflow_run = relationship("WorkflowRun", back_populates="validation_reports")
    checks = relationship("ValidationCheck", back_populates="report", cascade="all, delete-orphan")


class ValidationCheck(Base):
    """Individual validation check result."""
    __tablename__ = "validation_checks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("validation_reports.id", ondelete="CASCADE"), nullable=False)
    check_name = Column(String(100), nullable=False)
    check_code = Column(String(50), nullable=False)
    passed = Column(Boolean, nullable=False)
    message = Column(Text, nullable=True)
    severity = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    report = relationship("ValidationReport", back_populates="checks")


class ApprovalDecision(Base):
    """Approval/rejection decision by placement officer."""
    __tablename__ = "approval_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_run_id = Column(UUID(as_uuid=True), ForeignKey("workflow_runs.id"), nullable=False, index=True)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    decision = Column(String(20), nullable=False)
    comments = Column(Text, nullable=True)
    edits = Column(JSONB, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), default=utcnow)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    workflow_run = relationship("WorkflowRun", back_populates="approval_decisions")
    reviewer = relationship("User")


class EvidenceRecord(Base):
    """Evidence record linking outputs to sources."""
    __tablename__ = "evidence_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    evidence_type = Column(String(50), nullable=False)
    source = Column(String(255), nullable=False)
    source_id = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    scope_tags = Column(ARRAY(Text), nullable=True)
    confidence = Column(Numeric(3, 2), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class Version(Base):
    """Versioned snapshot of student readiness plan."""
    __tablename__ = "versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    version_number = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)
    snapshot = Column(JSONB, nullable=False)
    workflow_run_id = Column(UUID(as_uuid=True), ForeignKey("workflow_runs.id"), nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    student = relationship("Student", back_populates="versions")


class AuditLog(Base):
    """Append-only audit trail."""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), default=utcnow, index=True)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    actor_type = Column(String(50), nullable=False)
    workflow_run_id = Column(UUID(as_uuid=True), ForeignKey("workflow_runs.id"), nullable=True, index=True)
    agent_name = Column(String(100), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(100), nullable=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    input_ref = Column(Text, nullable=True)
    output_ref = Column(Text, nullable=True)
    decision = Column(String(50), nullable=True)
    validation_result = Column(String(50), nullable=True)
    approval_decision = Column(String(50), nullable=True)
    version = Column(Integer, nullable=True)
    correlation_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    details = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class KnowledgeDocument(Base):
    """Lab 4 knowledge base: role guides, job descriptions and learning resources (full-text indexed)."""
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        Index("ix_knowledge_documents_search", "search_vector", postgresql_using="gin"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_type = Column(String(30), nullable=False, index=True)  # role_guide | job_description | learning_resource
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String(255), nullable=False)
    url = Column(String(500), nullable=True)
    role_family = Column(String(50), nullable=True, index=True)
    tags = Column(ARRAY(Text), nullable=True)
    search_vector = Column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, ''))", persisted=True),
    )
    created_at = Column(DateTime(timezone=True), default=utcnow)
