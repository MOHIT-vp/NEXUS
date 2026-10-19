"""Models package — import all models so Alembic can discover them."""
from app.models.user import User, Student, PlacementOfficer, Consent, RevokedToken
from app.models.profile import (
    Resume, StudentProfile, Skill, StudentSkill,
    StudentProject, StudentExperience,
)
from app.models.company import Company, Job, RoleSkill, SkillBenchmark, ScoringConfig
from app.models.analysis import (
    CodingAnalytics, SkillGapReport, SkillGapItem,
    ReadinessScore, ScoreBreakdown, CompanyMatch,
    InterviewSession, InterviewQuestion, InterviewResponse,
    Roadmap, RoadmapItem,
)
from app.models.workflow import (
    WorkflowRun, AgentExecution, ValidationReport, ValidationCheck,
    ApprovalDecision, EvidenceRecord, Version, AuditLog, KnowledgeDocument,
)

__all__ = [
    "User", "Student", "PlacementOfficer", "Consent", "RevokedToken",
    "Resume", "StudentProfile", "Skill", "StudentSkill",
    "StudentProject", "StudentExperience",
    "Company", "Job", "RoleSkill", "SkillBenchmark", "ScoringConfig",
    "CodingAnalytics", "SkillGapReport", "SkillGapItem",
    "ReadinessScore", "ScoreBreakdown", "CompanyMatch",
    "InterviewSession", "InterviewQuestion", "InterviewResponse",
    "Roadmap", "RoadmapItem",
    "WorkflowRun", "AgentExecution", "ValidationReport", "ValidationCheck",
    "ApprovalDecision", "EvidenceRecord", "Version", "AuditLog", "KnowledgeDocument",
]
