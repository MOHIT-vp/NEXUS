"""
Service for managing companies, campus recruitment drives, and student preparedness evaluations.
Deterministic scoring, skill matching, and tailored pre-drive action roadmaps.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.company import (
    CompanyCreate,
    CompanyUpdate,
    JobDriveResponse,
    PreparednessCheckRequest,
    PreparednessCheckResponse,
    SkillGapDetail,
    CohortReadinessResponse,
    RecruitmentRound,
)

# ---------------------------------------------------------------------------
# Canonical Skill Normalization & Aliases
# ---------------------------------------------------------------------------

CANONICAL_SKILL_MAP: Dict[str, str] = {
    "react": "react.js",
    "reactjs": "react.js",
    "react.js": "react.js",
    "node": "node.js",
    "nodejs": "node.js",
    "node.js": "node.js",
    "python3": "python",
    "py": "python",
    "python": "python",
    "js": "javascript",
    "javascript": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    "java8": "java",
    "java": "java",
    "c++11": "c++",
    "cpp": "c++",
    "c++": "c++",
    "c#": "c#",
    "csharp": "c#",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "aws": "aws",
    "amazon web services": "aws",
    "ml": "machine learning",
    "machine learning": "machine learning",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "sql": "sql",
    "dsa": "data structures",
    "data structures": "data structures",
    "algorithms": "algorithms",
    "docker": "docker",
    "git": "git",
    "github": "git",
    "linux": "linux",
    "bash": "linux",
}


def canonicalize_skill(skill: str) -> str:
    """Normalize skill string into lowercase canonical format for robust matching."""
    if not skill:
        return ""
    clean = skill.strip().lower()
    return CANONICAL_SKILL_MAP.get(clean, clean)


# ---------------------------------------------------------------------------
# Seed Recruitment Drives
# ---------------------------------------------------------------------------

INITIAL_RECRUITMENT_DRIVES: List[Dict[str, Any]] = [
    {
        "job_id": "job-001",
        "company_id": "comp-001",
        "company_name": "TechCorp Solutions",
        "industry": "Enterprise Software",
        "website": "https://techcorp.example.com",
        "location": "Bengaluru, India (Hybrid)",
        "description": "Full-stack development role delivering high-scale SaaS applications for global financial customers.",
        "role_title": "Software Engineer",
        "role_family": "software_engineering",
        "package_lpa": 12.0,
        "min_cgpa": 7.0,
        "max_backlogs": 0,
        "min_experience": 0,
        "required_skills": ["Python", "JavaScript", "React.js", "SQL", "Git"],
        "preferred_skills": ["Docker", "AWS", "System Design"],
        "drive_date": "2026-10-10",
        "deadline": "2026-10-01",
        "status": "active",
        "selection_rounds": [
            {"round_number": 1, "name": "Online Coding Assessment", "type": "coding_test", "description": "DSA problems on arrays, strings, and hash maps", "duration_minutes": 90},
            {"round_number": 2, "name": "Technical Interview - Core CS", "type": "technical_interview", "description": "OOP, DBMS queries, OS concepts", "duration_minutes": 60},
            {"round_number": 3, "name": "Technical Interview - Projects", "type": "technical_interview", "description": "Architecture, code walkthrough and stack questions", "duration_minutes": 60},
            {"round_number": 4, "name": "HR & Culture Round", "type": "hr", "description": "Behavioral assessment and company alignment", "duration_minutes": 30},
        ],
        "created_at": "2026-09-01T10:00:00Z",
    },
    {
        "job_id": "job-002",
        "company_id": "comp-002",
        "company_name": "DataDriven Inc.",
        "industry": "Big Data & AI",
        "website": "https://datadriven.example.com",
        "location": "Hyderabad, India",
        "description": "Building real-time ETL pipelines, data warehouses, and streaming analytics pipelines.",
        "role_title": "Data Engineer",
        "role_family": "data_engineering",
        "package_lpa": 15.0,
        "min_cgpa": 7.5,
        "max_backlogs": 0,
        "min_experience": 0,
        "required_skills": ["Python", "SQL", "Data Structures", "Algorithms"],
        "preferred_skills": ["Machine Learning", "Apache Spark", "AWS"],
        "drive_date": "2026-10-18",
        "deadline": "2026-10-08",
        "status": "upcoming",
        "selection_rounds": [
            {"round_number": 1, "name": "Data Analytics & SQL Test", "type": "coding_test", "description": "Complex SQL queries, window functions, and algorithmic puzzle", "duration_minutes": 75},
            {"round_number": 2, "name": "Data Engineering Technical Round", "type": "technical_interview", "description": "ETL pipelines, schema design, and Spark concepts", "duration_minutes": 60},
            {"round_number": 3, "name": "Leadership & Fitment", "type": "hr", "description": "Problem-solving attitude and cultural fit", "duration_minutes": 45},
        ],
        "created_at": "2026-09-05T12:00:00Z",
    },
    {
        "job_id": "job-003",
        "company_id": "comp-003",
        "company_name": "InnovateTech",
        "industry": "Cloud Architecture",
        "website": "https://innovatetech.example.com",
        "location": "Pune, India",
        "description": "Designing high-throughput asynchronous backend microservices and RESTful / gRPC APIs.",
        "role_title": "Backend Developer",
        "role_family": "software_engineering",
        "package_lpa": 10.5,
        "min_cgpa": 6.5,
        "max_backlogs": 0,
        "min_experience": 0,
        "required_skills": ["Python", "Node.js", "SQL", "Git"],
        "preferred_skills": ["Docker", "Kubernetes", "Redis"],
        "drive_date": "2026-10-25",
        "deadline": "2026-10-15",
        "status": "upcoming",
        "selection_rounds": [
            {"round_number": 1, "name": "Aptitude & Coding Round", "type": "coding_test", "description": "Backend coding challenges and async logic", "duration_minutes": 90},
            {"round_number": 2, "name": "System & API Design", "type": "technical_interview", "description": "REST principles, caching with Redis, indexing", "duration_minutes": 60},
            {"round_number": 3, "name": "HR Discussion", "type": "hr", "description": "Communication and terms", "duration_minutes": 30},
        ],
        "created_at": "2026-09-10T14:00:00Z",
    },
    {
        "job_id": "job-004",
        "company_id": "comp-004",
        "company_name": "CloudFirst Systems",
        "industry": "Cloud & DevOps",
        "website": "https://cloudfirst.example.com",
        "location": "Bengaluru, India",
        "description": "Automating cloud infrastructure, CI/CD pipelines, container orchestration, and Kubernetes clusters.",
        "role_title": "DevOps Engineer",
        "role_family": "devops",
        "package_lpa": 14.0,
        "min_cgpa": 7.0,
        "max_backlogs": 0,
        "min_experience": 0,
        "required_skills": ["Docker", "Kubernetes", "AWS", "Linux", "Git"],
        "preferred_skills": ["Terraform", "Python", "CI/CD"],
        "drive_date": "2026-11-02",
        "deadline": "2026-10-22",
        "status": "upcoming",
        "selection_rounds": [
            {"round_number": 1, "name": "Linux & Cloud Scripting", "type": "coding_test", "description": "Bash scripting, Dockerfile optimization, and Linux internals", "duration_minutes": 60},
            {"round_number": 2, "name": "DevOps Architecture Round", "type": "technical_interview", "description": "K8s architecture, AWS networking, and Terraform pipelines", "duration_minutes": 60},
            {"round_number": 3, "name": "Managerial Discussion", "type": "hr", "description": "Incident management and ownership mindset", "duration_minutes": 30},
        ],
        "created_at": "2026-09-12T09:00:00Z",
    },
    {
        "job_id": "job-005",
        "company_id": "comp-005",
        "company_name": "FinSecure Analytics",
        "industry": "Fintech & Security",
        "website": "https://finsecure.example.com",
        "location": "Mumbai, India",
        "description": "Building low-latency, tamper-proof payment processing and wealth management web portals.",
        "role_title": "Full Stack Developer",
        "role_family": "software_engineering",
        "package_lpa": 13.5,
        "min_cgpa": 7.0,
        "max_backlogs": 0,
        "min_experience": 0,
        "required_skills": ["React.js", "Node.js", "JavaScript", "SQL"],
        "preferred_skills": ["TypeScript", "PostgreSQL", "Redis"],
        "drive_date": "2026-11-10",
        "deadline": "2026-10-30",
        "status": "upcoming",
        "selection_rounds": [
            {"round_number": 1, "name": "Full Stack Machine Test", "type": "coding_test", "description": "Build a responsive mini-component with API integration", "duration_minutes": 120},
            {"round_number": 2, "name": "Technical Deep Dive", "type": "technical_interview", "description": "State management, React hooks, SQL optimization", "duration_minutes": 60},
            {"round_number": 3, "name": "Culture & HR", "type": "hr", "description": "Ethics, compliance, and career aspirations", "duration_minutes": 30},
        ],
        "created_at": "2026-09-15T11:00:00Z",
    },
]


# In-memory store for fast lookup and standalone operation
_DRIVES_STORE: Dict[str, Dict[str, Any]] = {d["job_id"]: dict(d) for d in INITIAL_RECRUITMENT_DRIVES}


# ---------------------------------------------------------------------------
# Service Class
# ---------------------------------------------------------------------------

class CompanyService:
    """Manages companies, recruitment drives, and student preparedness."""

    @staticmethod
    def list_drives(
        search: Optional[str] = None,
        role_family: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[JobDriveResponse]:
        """List all listed recruitment drives matching query filters."""
        drives = list(_DRIVES_STORE.values())

        # Sort by creation date or drive date
        drives.sort(key=lambda d: d.get("drive_date") or d.get("created_at", ""), reverse=False)

        results = []
        for d in drives:
            # Search filter (name, role, skills)
            if search:
                term = search.lower().strip()
                matches_search = (
                    term in d["company_name"].lower()
                    or term in d["role_title"].lower()
                    or any(term in s.lower() for s in d.get("required_skills", []))
                    or any(term in s.lower() for s in d.get("preferred_skills", []))
                )
                if not matches_search:
                    continue

            # Role family filter
            if role_family and role_family.lower() != "all":
                if d.get("role_family", "").lower() != role_family.lower():
                    continue

            # Status filter
            if status and status.lower() != "all":
                if d.get("status", "").lower() != status.lower():
                    continue

            results.append(JobDriveResponse(
                job_id=d["job_id"],
                company_id=d["company_id"],
                company_name=d["company_name"],
                industry=d.get("industry"),
                website=d.get("website"),
                location=d.get("location"),
                description=d.get("description"),
                role_title=d["role_title"],
                role_family=d.get("role_family", "software_engineering"),
                package_lpa=float(d.get("package_lpa", 0.0)),
                min_cgpa=float(d.get("min_cgpa", 0.0)),
                max_backlogs=int(d.get("max_backlogs", 0)),
                min_experience=int(d.get("min_experience", 0)),
                required_skills=d.get("required_skills", []),
                preferred_skills=d.get("preferred_skills", []),
                drive_date=d.get("drive_date"),
                deadline=d.get("deadline"),
                status=d.get("status", "upcoming"),
                selection_rounds=[RecruitmentRound(**r) for r in (d.get("selection_rounds") or [])],
                created_at=d.get("created_at"),
            ))

        return results

    @staticmethod
    def get_drive(job_id: str) -> Optional[JobDriveResponse]:
        """
        Fetch a single recruitment drive by job_id, slug, or company name.
        Gracefully handles fuzzy slug matching (e.g. 'job-techcorp-solutions' or 'TechCorp Solutions').
        """
        d = _DRIVES_STORE.get(job_id)
        if not d:
            # Fallback 1: case-insensitive ID match
            for k, v in _DRIVES_STORE.items():
                if k.lower() == job_id.lower():
                    d = v
                    break
        if not d:
            # Fallback 2: slug or company name match
            clean_id = job_id.lower().replace("job-", "").replace("-", " ").strip()
            for v in _DRIVES_STORE.values():
                comp_clean = v.get("company_name", "").lower()
                if clean_id == comp_clean or clean_id in comp_clean or comp_clean in clean_id:
                    d = v
                    break

        if not d:
            return None

        return JobDriveResponse(
            job_id=d["job_id"],
            company_id=d["company_id"],
            company_name=d["company_name"],
            industry=d.get("industry"),
            website=d.get("website"),
            location=d.get("location"),
            description=d.get("description"),
            role_title=d["role_title"],
            role_family=d.get("role_family", "software_engineering"),
            package_lpa=float(d.get("package_lpa", 0.0)),
            min_cgpa=float(d.get("min_cgpa", 0.0)),
            max_backlogs=int(d.get("max_backlogs", 0)),
            min_experience=int(d.get("min_experience", 0)),
            required_skills=d.get("required_skills", []),
            preferred_skills=d.get("preferred_skills", []),
            drive_date=d.get("drive_date"),
            deadline=d.get("deadline"),
            status=d.get("status", "upcoming"),
            selection_rounds=[RecruitmentRound(**r) for r in (d.get("selection_rounds") or [])],
            created_at=d.get("created_at"),
        )

    @staticmethod
    def get_or_create_adhoc_drive(job_id: str, default_company: Optional[str] = None) -> JobDriveResponse:
        """Ensures a drive entry exists so ad-hoc preparedness checks never 404."""
        existing = CompanyService.get_drive(job_id)
        if existing:
            return existing

        company_name = default_company or job_id.replace("job-", "").replace("-", " ").title()
        adhoc_entry = {
            "job_id": job_id,
            "company_id": f"comp-{uuid.uuid4().hex[:8]}",
            "company_name": company_name,
            "industry": "Technology",
            "website": None,
            "location": "Bengaluru, India",
            "description": f"Recruitment drive for Software Engineer at {company_name}.",
            "role_title": "Software Engineer",
            "role_family": "software_engineering",
            "package_lpa": 12.0,
            "min_cgpa": 7.0,
            "max_backlogs": 0,
            "min_experience": 0,
            "required_skills": ["Python", "SQL", "Data Structures", "Git"],
            "preferred_skills": ["Docker", "AWS"],
            "drive_date": None,
            "deadline": None,
            "status": "upcoming",
            "selection_rounds": [
                {"round_number": 1, "name": "Online Coding Assessment", "type": "coding_test", "description": "DSA and coding", "duration_minutes": 90},
                {"round_number": 2, "name": "Technical Interview", "type": "technical_interview", "description": "Core CS and problem solving", "duration_minutes": 60},
                {"round_number": 3, "name": "HR Round", "type": "hr", "description": "Behavioral alignment", "duration_minutes": 30},
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _DRIVES_STORE[job_id] = adhoc_entry
        return CompanyService.get_drive(job_id)  # type: ignore

    @staticmethod
    def create_drive(payload: CompanyCreate) -> JobDriveResponse:
        """Placement cell lists a new company and recruitment drive."""
        new_job_id = f"job-{uuid.uuid4().hex[:8]}"
        new_comp_id = f"comp-{uuid.uuid4().hex[:8]}"

        # Default selection rounds if not provided
        rounds = []
        if payload.selection_rounds:
            rounds = [r.model_dump() for r in payload.selection_rounds]
        else:
            rounds = [
                {"round_number": 1, "name": "Online Technical Test", "type": "coding_test", "description": "Assessment covering domain basics and problem solving", "duration_minutes": 60},
                {"round_number": 2, "name": "Technical Interview", "type": "technical_interview", "description": "Deep dive into required skills and project architecture", "duration_minutes": 45},
                {"round_number": 3, "name": "HR & Fitment Interview", "type": "hr", "description": "Personality, communication, and college placement clearance", "duration_minutes": 30},
            ]

        entry = {
            "job_id": new_job_id,
            "company_id": new_comp_id,
            "company_name": payload.name.strip(),
            "industry": payload.industry,
            "website": payload.website,
            "location": payload.location,
            "description": payload.description or f"Recruitment drive for {payload.role_title} at {payload.name}.",
            "role_title": payload.role_title.strip(),
            "role_family": payload.role_family,
            "package_lpa": float(payload.package_lpa),
            "min_cgpa": float(payload.min_cgpa),
            "max_backlogs": int(payload.max_backlogs),
            "min_experience": int(payload.min_experience),
            "required_skills": [s.strip() for s in payload.required_skills if s.strip()],
            "preferred_skills": [s.strip() for s in payload.preferred_skills if s.strip()],
            "drive_date": payload.drive_date,
            "deadline": payload.deadline,
            "status": payload.status or "upcoming",
            "selection_rounds": rounds,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        _DRIVES_STORE[new_job_id] = entry

        return JobDriveResponse(
            job_id=entry["job_id"],
            company_id=entry["company_id"],
            company_name=entry["company_name"],
            industry=entry.get("industry"),
            website=entry.get("website"),
            location=entry.get("location"),
            description=entry.get("description"),
            role_title=entry["role_title"],
            role_family=entry["role_family"],
            package_lpa=entry["package_lpa"],
            min_cgpa=entry["min_cgpa"],
            max_backlogs=entry["max_backlogs"],
            min_experience=entry["min_experience"],
            required_skills=entry["required_skills"],
            preferred_skills=entry["preferred_skills"],
            drive_date=entry.get("drive_date"),
            deadline=entry.get("deadline"),
            status=entry.get("status", "upcoming"),
            selection_rounds=[RecruitmentRound(**r) for r in (entry.get("selection_rounds") or [])],
            created_at=entry.get("created_at"),
        )

    @staticmethod
    def update_drive(job_id: str, payload: CompanyUpdate) -> Optional[JobDriveResponse]:
        """Update an existing recruitment drive."""
        d = _DRIVES_STORE.get(job_id)
        if not d:
            return None

        update_dict = payload.model_dump(exclude_unset=True)
        for k, v in update_dict.items():
            if k == "selection_rounds" and v is not None:
                d["selection_rounds"] = [r if isinstance(r, dict) else r.model_dump() for r in v]
            elif v is not None:
                d[k] = v

        _DRIVES_STORE[job_id] = d
        return CompanyService.get_drive(job_id)

    @staticmethod
    def delete_drive(job_id: str) -> bool:
        """Delete a listed recruitment drive."""
        if job_id in _DRIVES_STORE:
            del _DRIVES_STORE[job_id]
            return True
        return False

    @staticmethod
    def get_all_jobs_for_matching() -> List[Dict[str, Any]]:
        """Used by JobMatchingAgent to match students against all listed drives."""
        return list(_DRIVES_STORE.values())

    # -----------------------------------------------------------------------
    # Deterministic Preparedness & Skill Match Evaluation Engine
    # -----------------------------------------------------------------------

    @staticmethod
    def evaluate_student_preparedness(
        job: Dict[str, Any],
        student_profile: Dict[str, Any],
        coding_analytics: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PreparednessCheckResponse:
        """
        Deterministic, mathematically sound preparedness assessment:
        1. Skill Coverage (max 40 pts):
           - Required skills: 85% base
           - Preferred skills: 15% bonus
           - Canonical skill normalization for robust matching
        2. Coding Activity & Problem Solving (max 25 pts)
        3. Project Relevance & Technical Depth (max 15 pts)
        4. Technical/Interview Readiness (max 15 pts)
        5. Academic Cutoff & Active Backlogs Verification (max 5 pts)
        """
        metadata = metadata or {}
        coding_analytics = coding_analytics or {}

        # 1. Academic Eligibility Check (CGPA & Backlogs)
        education = student_profile.get("education") or {}
        student_gpa = None
        if isinstance(education, dict) and education.get("gpa") is not None:
            try:
                student_gpa = float(education.get("gpa"))
            except (ValueError, TypeError):
                student_gpa = None
        elif metadata.get("cgpa") is not None:
            try:
                student_gpa = float(metadata.get("cgpa"))
            except (ValueError, TypeError):
                student_gpa = None

        min_cgpa = float(job.get("min_cgpa", 0.0))
        max_backlogs = int(job.get("max_backlogs", 0))

        student_backlogs = None
        if metadata.get("backlogs") is not None:
            try:
                student_backlogs = int(metadata.get("backlogs"))
            except (ValueError, TypeError):
                student_backlogs = None

        is_cgpa_eligible = True
        eligibility_reasons = []

        if student_gpa is not None and min_cgpa > 0:
            if student_gpa < min_cgpa:
                is_cgpa_eligible = False
                eligibility_reasons.append(
                    f"Current CGPA {student_gpa:.2f} is below the company cutoff of {min_cgpa:.2f}"
                )
            else:
                eligibility_reasons.append(
                    f"Meets academic eligibility: CGPA {student_gpa:.2f} >= {min_cgpa:.2f}"
                )
        else:
            eligibility_reasons.append(f"Cutoff criteria: {min_cgpa:.2f} CGPA (no candidate GPA on file)")

        is_backlog_eligible = True
        if student_backlogs is not None:
            if student_backlogs > max_backlogs:
                is_backlog_eligible = False
                eligibility_reasons.append(
                    f"Active backlogs count ({student_backlogs}) exceeds drive maximum allowed ({max_backlogs})"
                )
            else:
                eligibility_reasons.append(
                    f"Meets backlog criteria: {student_backlogs} active backlog(s) (max allowed: {max_backlogs})"
                )
        else:
            eligibility_reasons.append(f"Backlog criteria: max {max_backlogs} allowed (no backlog record provided)")

        is_fully_eligible = is_cgpa_eligible and is_backlog_eligible
        is_eligible = is_fully_eligible
        eligibility_pts = 5.0 if is_eligible else 0.0

        # 2. Canonical Skill Matching & Coverage
        student_skills = student_profile.get("skills", [])
        skill_dict: Dict[str, str] = {}
        for s in student_skills:
            if isinstance(s, dict):
                s_name = s.get("name", "")
                prof = s.get("proficiency", "intermediate")
            elif isinstance(s, str):
                s_name = s
                prof = "intermediate"
            else:
                continue
            if s_name:
                skill_dict[canonicalize_skill(s_name)] = prof
                skill_dict[s_name.lower().strip()] = prof

        required_skills = [s.strip() for s in job.get("required_skills", []) if s.strip()]
        preferred_skills = [s.strip() for s in job.get("preferred_skills", []) if s.strip()]

        matched_skills: List[Dict[str, Any]] = []
        missing_skills: List[SkillGapDetail] = []

        req_matched_count = 0
        for req in required_skills:
            req_canon = canonicalize_skill(req)
            raw_clean = req.lower().strip()
            if req_canon in skill_dict or raw_clean in skill_dict:
                req_matched_count += 1
                matched_skills.append({
                    "name": req,
                    "type": "required",
                    "proficiency": skill_dict.get(req_canon) or skill_dict.get(raw_clean, "intermediate"),
                    "status": "matched",
                })

        req_ratio = (req_matched_count / len(required_skills)) if required_skills else 1.0

        for req in required_skills:
            req_canon = canonicalize_skill(req)
            raw_clean = req.lower().strip()
            if req_canon not in skill_dict and raw_clean not in skill_dict:
                missing_skills.append(SkillGapDetail(
                    skill=req,
                    importance="required",
                    severity="critical" if req_ratio < 0.5 else "high",
                    recommendation=f"Prioritize mastering {req} core patterns and standard interview coding questions before the drive.",
                    learning_resource=CompanyService._get_learning_resource(req),
                    estimated_hours=12,
                ))

        pref_matched_count = 0
        for pref in preferred_skills:
            pref_canon = canonicalize_skill(pref)
            raw_clean = pref.lower().strip()
            if pref_canon in skill_dict or raw_clean in skill_dict:
                pref_matched_count += 1
                matched_skills.append({
                    "name": pref,
                    "type": "preferred",
                    "proficiency": skill_dict.get(pref_canon) or skill_dict.get(raw_clean, "intermediate"),
                    "status": "matched",
                })
            else:
                missing_skills.append(SkillGapDetail(
                    skill=pref,
                    importance="preferred",
                    severity="medium",
                    recommendation=f"Review fundamental concepts and hands-on examples of {pref} as a competitive differentiator.",
                    learning_resource=CompanyService._get_learning_resource(pref),
                    estimated_hours=8,
                ))

        pref_ratio = (pref_matched_count / len(preferred_skills)) if preferred_skills else 1.0

        skill_base = req_ratio * 40.0 * 0.85
        skill_bonus = pref_ratio * 40.0 * 0.15
        skill_coverage_pts = round(min(skill_base + skill_bonus, 40.0), 1)

        # 3. Coding Performance (max 25 pts)
        summary = coding_analytics.get("summary", {}) if coding_analytics else {}
        percentile = summary.get("coding_percentile")
        coding_solved = metadata.get("coding_solved", 0)

        if percentile is not None and percentile > 0:
            coding_pts = round((percentile / 100.0) * 25.0, 1)
        elif coding_solved > 0:
            approx_pct = min(max((coding_solved / 250.0) * 85.0, 30.0), 98.0)
            coding_pts = round((approx_pct / 100.0) * 25.0, 1)
        else:
            coding_pts = 12.5  # Neutral baseline

        # 4. Project Relevance (max 15 pts)
        projects = student_profile.get("projects", [])
        all_job_skills_canon = {canonicalize_skill(s) for s in required_skills + preferred_skills}
        matching_proj_count = 0
        tech_match_count = 0

        for p in projects:
            techs = {canonicalize_skill(t) for t in p.get("technologies", [])}
            overlap = techs & all_job_skills_canon
            if overlap:
                matching_proj_count += 1
                tech_match_count += len(overlap)

        if projects:
            proj_ratio = matching_proj_count / len(projects)
            depth_ratio = min(tech_match_count / max(len(all_job_skills_canon), 1), 1.0)
            project_pts = round(((proj_ratio * 0.6) + (depth_ratio * 0.4)) * 15.0, 1)
        else:
            project_pts = 5.0

        # 5. Technical Depth & Interview Readiness (max 15 pts)
        advanced_count = sum(1 for s in student_skills if isinstance(s, dict) and s.get("proficiency") in ("advanced", "expert"))
        interview_readiness_pts = round(min(7.5 + (advanced_count * 1.5) + (req_ratio * 5.0), 15.0), 1)

        # Overall Score
        overall_score = round(
            skill_coverage_pts + coding_pts + project_pts + interview_readiness_pts + eligibility_pts,
            1
        )
        max_score = 100.0
        match_percentage = round((overall_score / max_score) * 100.0, 1)

        # Match Tier
        if overall_score >= 75 and is_eligible:
            match_tier = "Highly Prepared"
        elif overall_score >= 55 and is_eligible:
            match_tier = "Competitive Fit"
        else:
            match_tier = "Preparation Needed"

        # Confidence Calculation
        conf_factors = [req_ratio, 1.0 if coding_pts > 14 else 0.5, 1.0 if is_eligible else 0.2]
        confidence = round(sum(conf_factors) / len(conf_factors), 2)

        # Fit Highlights
        fit_highlights = []
        if req_ratio >= 0.8:
            fit_highlights.append(f"Strong required skill match: {req_matched_count}/{len(required_skills)} core skills verified.")
        elif req_matched_count > 0:
            fit_highlights.append(f"Possesses core foundation in {', '.join([m['name'] for m in matched_skills[:3]])}.")

        if coding_pts >= 18:
            fit_highlights.append("Strong problem-solving capability likely to clear Online Assessment rounds.")

        if matching_proj_count > 0:
            target_comp = job.get("company_name") or job.get("name", "the target company")
            fit_highlights.append(f"Hands-on project work utilizing tech relevant to {target_comp}.")

        if not fit_highlights:
            fit_highlights.append("Meets entry prerequisites with room to strengthen domain match.")

        # Concern Areas
        concern_areas = []
        if not is_cgpa_eligible:
            concern_areas.append(f"Academic cutoff shortfall: minimum required CGPA is {min_cgpa:.2f}.")

        if not is_backlog_eligible and student_backlogs is not None:
            concern_areas.append(f"Backlog clearance required: active backlogs ({student_backlogs}) exceed cutoff of {max_backlogs}.")

        if missing_skills:
            critical_missing = [m.skill for m in missing_skills if m.importance == "required"]
            if critical_missing:
                concern_areas.append(f"Missing mandatory requirements: {', '.join(critical_missing[:3])}.")

        if coding_pts < 15:
            concern_areas.append("Coding test practice recommended: solve standard medium-level company problems.")

        if not concern_areas:
            concern_areas.append("No major roadblocks detected. Maintain coding consistency and practice interview communication.")

        # Targeted 2-Week Pre-Drive Action Plan
        prep_roadmap = CompanyService._generate_company_prep_roadmap(
            job=job,
            missing_skills=missing_skills,
            is_eligible=is_eligible,
        )

        raw_rounds = job.get("selection_rounds") or []
        rounds_list = [
            r if isinstance(r, RecruitmentRound) else RecruitmentRound(**r)
            for r in raw_rounds
        ]

        resolved_job_id = job.get("job_id") or f"job-{uuid.uuid4().hex[:8]}"
        resolved_company_name = job.get("company_name") or job.get("name", "Target Company")
        resolved_role_title = job.get("role_title", "Software Engineer")

        return PreparednessCheckResponse(
            job_id=resolved_job_id,
            company_name=resolved_company_name,
            role_title=resolved_role_title,
            role_family=job.get("role_family", "software_engineering"),
            package_lpa=float(job.get("package_lpa", 0.0)),
            min_cgpa=min_cgpa,
            max_backlogs=max_backlogs,
            student_cgpa=student_gpa,
            student_backlogs=student_backlogs,
            student_coding_solved=coding_solved if coding_solved else None,
            is_cgpa_eligible=is_cgpa_eligible,
            is_backlog_eligible=is_backlog_eligible,
            is_fully_eligible=is_fully_eligible,
            is_eligible=is_eligible,
            eligibility_reasons=eligibility_reasons,
            overall_score=overall_score,
            max_score=max_score,
            match_percentage=match_percentage,
            match_tier=match_tier,
            confidence=confidence,
            breakdown={
                "skill_coverage": {"score": skill_coverage_pts, "max": 40.0, "percentage": round((skill_coverage_pts / 40.0) * 100, 1)},
                "coding_performance": {"score": coding_pts, "max": 25.0, "percentage": round((coding_pts / 25.0) * 100, 1)},
                "project_relevance": {"score": project_pts, "max": 15.0, "percentage": round((project_pts / 15.0) * 100, 1)},
                "interview_readiness": {"score": interview_readiness_pts, "max": 15.0, "percentage": round((interview_readiness_pts / 15.0) * 100, 1)},
                "academic_eligibility": {"score": eligibility_pts, "max": 5.0, "percentage": round((eligibility_pts / 5.0) * 100, 1)},
            },
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            fit_highlights=fit_highlights,
            concern_areas=concern_areas,
            prep_roadmap=prep_roadmap,
            selection_rounds=rounds_list,
        )

    @staticmethod
    def _generate_company_prep_roadmap(
        job: Dict[str, Any],
        missing_skills: List[SkillGapDetail],
        is_eligible: bool,
    ) -> List[Dict[str, Any]]:
        """Generates an actionable step-by-step roadmap specifically tailored for this recruitment drive."""
        roadmap = []
        missing_names = [m.skill for m in missing_skills if m.importance == "required"]
        pref_missing_names = [m.skill for m in missing_skills if m.importance == "preferred"]
        company = job.get("company_name") or job.get("name", "Company")

        # Week 1: Missing Core Skills & DSA test practice
        if missing_names:
            top_skill = missing_names[0]
            roadmap.append({
                "week": 1,
                "focus_area": f"Core Gap Closure: {top_skill}",
                "action_item": f"Complete fundamental tutorials and build an end-to-end sandbox module using {top_skill}.",
                "resource": CompanyService._get_learning_resource(top_skill),
                "estimated_hours": 14,
                "priority": "critical",
            })
        elif pref_missing_names:
            top_pref = pref_missing_names[0]
            roadmap.append({
                "week": 1,
                "focus_area": f"Preferred Skill Edge: {top_pref}",
                "action_item": f"Build practical hands-on mini-module utilizing {top_pref} to stand out against competition.",
                "resource": CompanyService._get_learning_resource(top_pref),
                "estimated_hours": 10,
                "priority": "high",
            })
        else:
            roadmap.append({
                "week": 1,
                "focus_area": "Coding Test Drills",
                "action_item": f"Solve 15-20 LeetCode Medium problems specifically tagged for {company} recruitment tests.",
                "resource": "LeetCode Top Interview Questions / NeetCode 150",
                "estimated_hours": 12,
                "priority": "high",
            })

        # Additional missing skill or second focus
        if len(missing_names) > 1:
            second_skill = missing_names[1]
            roadmap.append({
                "week": 1,
                "focus_area": f"Secondary Skill: {second_skill}",
                "action_item": f"Learn practical usage, configurations, and core architectural patterns for {second_skill}.",
                "resource": CompanyService._get_learning_resource(second_skill),
                "estimated_hours": 10,
                "priority": "high",
            })

        # Week 2: Projects, Mock Interview, and Company Domain Questions
        roadmap.append({
            "week": 2,
            "focus_area": f"{company} Technical Interview Prep",
            "action_item": f"Review project code repos, prepare explanations of tradeoffs, and practice CS fundamentals (OS, DBMS, System Design).",
            "resource": "Grokking System Design & CS Fundamentals Checklist",
            "estimated_hours": 12,
            "priority": "high",
        })

        roadmap.append({
            "week": 2,
            "focus_area": "Mock Interview & Behavioral Alignment",
            "action_item": f"Conduct 2 peer mock interviews focusing on STAR method for {company}'s leadership principles and cultural fit.",
            "resource": "NEXUS AI Career Assistant & PRAMA Mock Simulator",
            "estimated_hours": 8,
            "priority": "medium",
        })

        return roadmap

    @staticmethod
    def _get_learning_resource(skill: str) -> str:
        """Helper to assign high-quality learning resources for specific skills."""
        s = skill.lower().strip()
        if "docker" in s:
            return "Docker Getting Started Tutorial & Play with Docker"
        if "kubernetes" in s or "k8s" in s:
            return "Kubernetes Basics Official Guide & KodeKloud Labs"
        if "aws" in s:
            return "AWS Skill Builder: Cloud Practitioner Essentials"
        if "react" in s:
            return "React.dev Interactive Documentation & Scrimba React Course"
        if "python" in s:
            return "Real Python & LeetCode Python 3 Track"
        if "sql" in s or "postgres" in s:
            return "Mode Analytics SQL Tutorial & LeetCode 50 SQL Study Plan"
        if "system design" in s:
            return "Alex Xu System Design Interview Volume 1 & Primer"
        if "machine learning" in s:
            return "Andrew Ng Machine Learning Specialization (Coursera)"
        if "node" in s:
            return "Node.js Official Guides & FullStackOpen Backend Track"
        if "git" in s:
            return "Pro Git Book (free online) & Oh My Git! interactive"
        if "linux" in s:
            return "Linux Journey (linuxjourney.com) Command Line Track"
        return f"Coursera / Udemy High-Rated Bootcamp on {skill}"

    @staticmethod
    def compute_cohort_readiness(job_id: str, student_profiles: Optional[List[Dict[str, Any]]] = None) -> CohortReadinessResponse:
        """
        Calculates cohort-wide analytics for placement officers:
        How many students in the college are eligible, average readiness, and common skill bottlenecks.
        """
        d = _DRIVES_STORE.get(job_id)
        if not d:
            raise ValueError(f"Recruitment drive {job_id} not found.")

        # Default sample student cohort if none passed from database
        if not student_profiles:
            student_profiles = [
                {
                    "student_id": "stud-demo-1",
                    "skills": [{"name": "Python", "proficiency": "advanced"}, {"name": "JavaScript", "proficiency": "intermediate"}, {"name": "React.js", "proficiency": "intermediate"}, {"name": "SQL", "proficiency": "intermediate"}, {"name": "Git", "proficiency": "intermediate"}],
                    "education": {"gpa": 8.4},
                    "projects": [{"title": "E-Commerce Microservice", "technologies": ["Python", "React.js", "SQL"]}],
                },
                {
                    "student_id": "stud-demo-2",
                    "skills": [{"name": "Python", "proficiency": "expert"}, {"name": "SQL", "proficiency": "advanced"}, {"name": "Docker", "proficiency": "intermediate"}, {"name": "Algorithms", "proficiency": "advanced"}],
                    "education": {"gpa": 7.8},
                    "projects": [{"title": "Data Pipeline", "technologies": ["Python", "SQL", "Docker"]}],
                },
                {
                    "student_id": "stud-demo-3",
                    "skills": [{"name": "Java", "proficiency": "intermediate"}, {"name": "SQL", "proficiency": "intermediate"}],
                    "education": {"gpa": 6.8},
                    "projects": [{"title": "Library App", "technologies": ["Java", "SQL"]}],
                },
                {
                    "student_id": "stud-demo-4",
                    "skills": [{"name": "Python", "proficiency": "intermediate"}, {"name": "React.js", "proficiency": "intermediate"}, {"name": "Git", "proficiency": "intermediate"}, {"name": "AWS", "proficiency": "beginner"}],
                    "education": {"gpa": 8.1},
                    "projects": [{"title": "Cloud Dashboard", "technologies": ["React.js", "AWS"]}],
                },
                {
                    "student_id": "stud-demo-5",
                    "skills": [{"name": "Node.js", "proficiency": "advanced"}, {"name": "JavaScript", "proficiency": "advanced"}, {"name": "React.js", "proficiency": "intermediate"}, {"name": "Git", "proficiency": "intermediate"}],
                    "education": {"gpa": 7.2},
                    "projects": [{"title": "Social Network", "technologies": ["Node.js", "React.js"]}],
                },
            ]

        total_students = len(student_profiles)
        eligible_count = 0
        total_score = 0.0
        high_fit = 0
        mod_fit = 0
        low_fit = 0
        missing_counter: Dict[str, int] = {}

        for profile in student_profiles:
            res = CompanyService.evaluate_student_preparedness(job=d, student_profile=profile)
            if res.is_eligible:
                eligible_count += 1
            total_score += res.overall_score

            if res.overall_score >= 75 and res.is_eligible:
                high_fit += 1
            elif res.overall_score >= 55 and res.is_eligible:
                mod_fit += 1
            else:
                low_fit += 1

            for m in res.missing_skills:
                if m.importance == "required":
                    missing_counter[m.skill] = missing_counter.get(m.skill, 0) + 1

        avg_score = round(total_score / max(total_students, 1), 1)
        eligible_pct = round((eligible_count / max(total_students, 1)) * 100.0, 1)

        common_missing = [
            {
                "skill": skill,
                "missing_count": count,
                "missing_percentage": round((count / max(total_students, 1)) * 100.0, 1),
            }
            for skill, count in sorted(missing_counter.items(), key=lambda x: x[1], reverse=True)
        ]

        return CohortReadinessResponse(
            job_id=d["job_id"],
            company_name=d["company_name"],
            role_title=d["role_title"],
            total_students_evaluated=total_students,
            eligible_count=eligible_count,
            eligible_percentage=eligible_pct,
            average_readiness_score=avg_score,
            high_fit_count=high_fit,
            moderate_fit_count=mod_fit,
            low_fit_count=low_fit,
            common_missing_skills=common_missing,
        )


company_service = CompanyService()
