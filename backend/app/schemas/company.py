"""
Schemas for Placement Cell Company & Recruitment Drives and Student Preparedness Check.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class RecruitmentRound(BaseModel):
    round_number: int
    name: str
    type: str = "technical_interview"  # coding_test, technical_interview, system_design, hr, aptitude
    description: Optional[str] = None
    duration_minutes: Optional[int] = 60


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Company name (e.g. Google, Goldman Sachs, TechCorp)")
    industry: Optional[str] = "Technology"
    website: Optional[str] = None
    location: Optional[str] = "Bengaluru, India"
    description: Optional[str] = None
    role_title: str = Field(..., min_length=1, description="Job role title (e.g. Software Engineer, Data Analyst)")
    role_family: str = Field(default="software_engineering", description="Role domain (software_engineering, data_engineering, devops, analytics, core)")
    package_lpa: float = Field(..., gt=0.0, description="Annual compensation package in LPA (e.g. 14.5)")
    min_cgpa: float = Field(default=7.0, ge=0.0, le=10.0, description="Minimum CGPA cutoff (0-10)")
    max_backlogs: int = Field(default=0, ge=0, description="Maximum allowed active backlogs")
    min_experience: int = Field(default=0, ge=0, description="Minimum years of experience")
    required_skills: List[str] = Field(default_factory=list, description="Mandatory required skills")
    preferred_skills: List[str] = Field(default_factory=list, description="Bonus / preferred skills")
    drive_date: Optional[str] = Field(None, description="Drive or recruitment event date (YYYY-MM-DD)")
    deadline: Optional[str] = Field(None, description="Application deadline (YYYY-MM-DD)")
    status: str = Field(default="upcoming", description="Drive status: upcoming, active, closed")
    selection_rounds: Optional[List[RecruitmentRound]] = Field(default=None, description="Interview and evaluation rounds")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid = {"upcoming", "active", "closed", "completed"}
        if v.lower() not in valid:
            raise ValueError(f"Status must be one of {valid}")
        return v.lower()

    @field_validator("required_skills", "preferred_skills", mode="before")
    @classmethod
    def clean_skills(cls, v: Any) -> List[str]:
        if not v:
            return []
        seen = set()
        cleaned = []
        for s in v:
            if isinstance(s, str):
                trimmed = s.strip()
                if trimmed and trimmed.lower() not in seen:
                    seen.add(trimmed.lower())
                    cleaned.append(trimmed)
        return cleaned


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    role_title: Optional[str] = None
    role_family: Optional[str] = None
    package_lpa: Optional[float] = Field(default=None, gt=0.0)
    min_cgpa: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    max_backlogs: Optional[int] = Field(default=None, ge=0)
    min_experience: Optional[int] = Field(default=None, ge=0)
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    drive_date: Optional[str] = None
    deadline: Optional[str] = None
    status: Optional[str] = None
    selection_rounds: Optional[List[RecruitmentRound]] = None


class JobDriveResponse(BaseModel):
    job_id: str
    company_id: str
    company_name: str
    industry: Optional[str] = None
    website: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    role_title: str
    role_family: str
    package_lpa: float
    min_cgpa: float
    max_backlogs: int = 0
    min_experience: int
    required_skills: List[str]
    preferred_skills: List[str]
    drive_date: Optional[str] = None
    deadline: Optional[str] = None
    status: str
    selection_rounds: List[RecruitmentRound] = []
    created_at: Optional[str] = None


class PreparednessCheckRequest(BaseModel):
    run_id: Optional[str] = Field(None, description="Workflow run ID from student's published plan")
    student_id: Optional[str] = Field(None, description="Student ID")
    skills: Optional[List[str]] = Field(None, description="Optional skills override for simulation or direct testing")
    cgpa: Optional[float] = Field(None, ge=0.0, le=10.0, description="Optional CGPA override")
    backlogs: Optional[int] = Field(None, ge=0, description="Optional active backlogs count")
    coding_solved: Optional[int] = Field(None, ge=0, description="Optional coding problems solved count")
    projects: Optional[List[Dict[str, Any]]] = Field(None, description="Optional projects for simulation")


class SkillGapDetail(BaseModel):
    skill: str
    importance: str  # required or preferred
    severity: str    # critical, high, medium
    recommendation: str
    learning_resource: str
    estimated_hours: int


class PreparednessCheckResponse(BaseModel):
    job_id: str
    company_name: str
    role_title: str
    role_family: str
    package_lpa: float
    min_cgpa: float
    max_backlogs: int = 0
    student_cgpa: Optional[float] = None
    student_backlogs: Optional[int] = None
    student_coding_solved: Optional[int] = None
    is_cgpa_eligible: bool = True
    is_backlog_eligible: bool = True
    is_fully_eligible: bool = True
    is_eligible: bool = True
    eligibility_reasons: List[str]
    overall_score: float
    max_score: float
    match_percentage: float
    match_tier: str  # Highly Prepared, Competitive Fit, Preparation Needed
    confidence: float
    breakdown: Dict[str, Any]
    matched_skills: List[Dict[str, Any]]
    missing_skills: List[SkillGapDetail]
    fit_highlights: List[str]
    concern_areas: List[str]
    prep_roadmap: List[Dict[str, Any]]
    selection_rounds: List[RecruitmentRound]


class CohortReadinessResponse(BaseModel):
    job_id: str
    company_name: str
    role_title: str
    total_students_evaluated: int
    eligible_count: int
    eligible_percentage: float
    average_readiness_score: float
    high_fit_count: int
    moderate_fit_count: int
    low_fit_count: int
    common_missing_skills: List[Dict[str, Any]]
