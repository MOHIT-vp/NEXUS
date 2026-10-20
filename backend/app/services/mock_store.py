"""
Mock Store Service for Placement Bot.

Provides an in-memory repository with realistic mock data and live state tracking.
Acts as a seamless fallback whenever PostgreSQL/asyncpg is unreachable or unavailable.
Allows the frontend, student dashboard, officer review portal, and admin panel
to function completely out-of-the-box with zero database dependency.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Default Seed Data
# ---------------------------------------------------------------------------

def _now_iso(offset_minutes: int = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(minutes=offset_minutes)
    return dt.isoformat()


DEMO_RUN_ID_1 = "c1a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c"  # Pending Review: Aditya C
DEMO_RUN_ID_2 = "d2b3c4d5-e6f7-4a8b-9c0d-1e2f3a4b5c6d"  # Published: Mohit Patil
DEMO_RUN_ID_3 = "e3c4d5e6-f7a8-4b9c-0d1e-2f3a4b5c6d7e"  # Published: Bhuwanesh S
DEMO_RUN_ID_4 = "f4d5e6f7-a8b9-4c0d-1e2f-3a4b5c6d7e8f"  # Pending Review: Rahul K

DEMO_STUDENT_ID_1 = "ad171a00-1111-4000-8000-000000000001"
DEMO_STUDENT_ID_2 = "ad171a00-1111-4000-8000-000000000002"
DEMO_STUDENT_ID_3 = "ad171a00-1111-4000-8000-000000000003"
DEMO_STUDENT_ID_4 = "ad171a00-1111-4000-8000-000000000004"


def _create_mock_snapshot_aditya() -> Dict[str, Any]:
    return {
        "student_profile": {
            "name": "Aditya C",
            "usn": "01FE23BCI043",
            "email": "aditya.c@kletech.ac.in",
            "education": {
                "degree": "B.Tech Computer Science & Engineering",
                "institution": "KLE Technological University",
                "gpa": 8.85,
                "graduation_year": 2026,
            },
            "skills": [
                {"name": "Python", "proficiency": "advanced"},
                {"name": "FastAPI", "proficiency": "advanced"},
                {"name": "React.js", "proficiency": "intermediate"},
                {"name": "TypeScript", "proficiency": "intermediate"},
                {"name": "PostgreSQL", "proficiency": "intermediate"},
                {"name": "PyTorch", "proficiency": "intermediate"},
                {"name": "LangGraph", "proficiency": "intermediate"},
                {"name": "Docker", "proficiency": "intermediate"},
                {"name": "Data Structures & Algorithms", "proficiency": "advanced"},
                {"name": "Git", "proficiency": "advanced"},
            ],
            "projects": [
                {
                    "title": "Placement Bot - Multi-Agent Placement Portal",
                    "technologies": ["FastAPI", "LangGraph", "Groq API", "Next.js", "pgvector"],
                    "description": "Autonomous multi-agent system analyzing student resumes, computing deterministic ATS matching scores, and generating tailored placement roadmaps.",
                },
                {
                    "title": "Distributed In-Memory Key-Value Store",
                    "technologies": ["Python", "AsyncIO", "Raft Consensus"],
                    "description": "High-throughput asynchronous distributed storage node with raft replication and write-ahead logging.",
                },
            ],
            "experience": [
                {
                    "role": "AI Engineering Intern",
                    "organization": "Campus Tech Labs",
                    "duration": "3 months",
                    "highlights": ["Built RAG pipeline using pgvector and LangChain", "Reduced inference latency by 35%"],
                }
            ],
        },
        "skill_gap_report": {
            "target_role": "Software Development Engineer (SDE-1)",
            "overall_match_percentage": 88.5,
            "strengths": ["Python", "FastAPI", "RESTful API Design", "Data Structures", "AsyncIO"],
            "missing_skills": ["Kubernetes", "System Design (Microservices)", "Redis Caching"],
            "recommendations": [
                "Complete a high-concurrency Redis caching module in a backend project.",
                "Review System Design Fundamentals: horizontal scaling, load balancers, rate limiting.",
            ],
        },
        "coding_analytics": {
            "leetcode_handle": "aditya_c_dev",
            "github_username": "adityac-dev",
            "coding_solved": 265,
            "contest_rating": 1740,
            "topic_distribution": {
                "Arrays & Hashing": 65,
                "Two Pointers & Sliding Window": 45,
                "Trees & Graphs": 55,
                "Dynamic Programming": 40,
                "Binary Search": 35,
                "Trie & Backtracking": 25,
            },
            "platform_verified": True,
        },
        "matching_result": {
            "target_domain": "software",
            "readiness_score": {
                "total": 88.5,
                "technical_score": 92.0,
                "coding_score": 85.0,
                "academic_score": 88.5,
                "fit_tier": "Highly Prepared",
            },
            "matches": [
                {
                    "job_id": "google-swe-2026",
                    "company_name": "Google",
                    "job_title": "Software Engineer (University Graduate)",
                    "package_lpa": 32.5,
                    "match_percentage": 89.0,
                    "matched_skills": ["Python", "Data Structures", "Algorithms", "Git"],
                    "missing_skills": ["Distributed Systems", "C++"],
                    "confidence": "0.92",
                },
                {
                    "job_id": "microsoft-swe-2026",
                    "company_name": "Microsoft",
                    "job_title": "Software Development Engineer - 1",
                    "package_lpa": 28.0,
                    "match_percentage": 91.5,
                    "matched_skills": ["Python", "FastAPI", "TypeScript", "React.js", "PostgreSQL"],
                    "missing_skills": ["Azure Cloud"],
                    "confidence": "0.94",
                },
                {
                    "job_id": "cisco-sde-2026",
                    "company_name": "Cisco",
                    "job_title": "Software Consulting Engineer",
                    "package_lpa": 19.5,
                    "match_percentage": 93.0,
                    "matched_skills": ["Python", "Networking Basics", "FastAPI", "Docker", "Git"],
                    "missing_skills": ["Kubernetes"],
                    "confidence": "0.95",
                },
                {
                    "job_id": "amazon-sde-2026",
                    "company_name": "Amazon",
                    "job_title": "Software Development Engineer",
                    "package_lpa": 30.0,
                    "match_percentage": 86.0,
                    "matched_skills": ["Python", "Data Structures", "Algorithms", "System Architecture"],
                    "missing_skills": ["AWS SDK", "High-Scale Concurrency"],
                    "confidence": "0.89",
                },
            ],
        },
        "interview_result": {
            "behavioral_readiness": 88,
            "technical_depth": 92,
            "problem_solving": 86,
            "mock_interview_recommendation": "Ready for Technical Round 1 and Machine Coding Rounds. Practice STAR method for Amazon Leadership Principles.",
        },
        "roadmap": {
            "roadmap_items": [
                {
                    "week": 1,
                    "focus_area": "Advanced Graphs & Dynamic Programming",
                    "action_item": "Solve 15 LeetCode Mediums covering BFS/DFS Dijkstra and 2D DP.",
                    "resource": "NeetCode 150 - Advanced Graphs Roadmap",
                    "estimated_hours": 12,
                    "priority": "high",
                },
                {
                    "week": 2,
                    "focus_area": "System Design & Distributed Patterns",
                    "action_item": "Study Rate Limiter, TinyURL, and Distributed Caching architectures.",
                    "resource": "Grokking Modern System Design",
                    "estimated_hours": 10,
                    "priority": "high",
                },
                {
                    "week": 3,
                    "focus_area": "Mock Technical Interviews",
                    "action_item": "Conduct 2 peer mock interviews focusing on edge case analysis and clean code.",
                    "resource": "Pramp / Campus Placement Cell Mock Sessions",
                    "estimated_hours": 6,
                    "priority": "medium",
                },
            ]
        },
        "resume_perfection": {
            "status": "completed",
            "evaluation": {
                "overall_score": 88,
                "tier_label": "Verified & Exceptional Match",
                "authenticity_index": 94,
                "evidence_strength": "High",
                "feedback": "All claimed technical competencies in FastAPI, LangGraph, and Distributed Systems verified with detailed evidence records and GitHub commits.",
            },
            "questions": [
                {
                    "id": "q1",
                    "topic": "FastAPI & LangGraph Pipeline",
                    "question": "How did you manage state persistence and checkpointing between agent nodes in your LangGraph implementation?",
                    "suggested_answer": "Used MemorySaver checkpointer for state preservation and transactional transition nodes.",
                },
                {
                    "id": "q2",
                    "topic": "Raft Consensus",
                    "question": "Explain how leader election handles network partition split-brain in your Distributed KV store.",
                    "suggested_answer": "Requires majority quorum (N/2 + 1) votes before committing log entries; isolated partition cannot commit.",
                },
            ],
        },
        "metadata": {
            "student_name": "Aditya C",
            "usn": "01FE23BCI043",
            "cgpa": 8.85,
            "coding_solved": 265,
            "validation_passed": True,
            "generated_at": _now_iso(30),
        },
    }


def _create_mock_snapshot_mohit() -> Dict[str, Any]:
    return {
        "student_profile": {
            "name": "Mohit Patil",
            "usn": "01FE23BCI081",
            "email": "mohit.patil@kletech.ac.in",
            "education": {
                "degree": "B.Tech Computer Science & Engineering",
                "institution": "KLE Technological University",
                "gpa": 8.70,
                "graduation_year": 2026,
            },
            "skills": [
                {"name": "Python", "proficiency": "advanced"},
                {"name": "SQL", "proficiency": "advanced"},
                {"name": "Apache Spark", "proficiency": "intermediate"},
                {"name": "PostgreSQL", "proficiency": "advanced"},
                {"name": "Docker", "proficiency": "intermediate"},
                {"name": "Data Pipelines", "proficiency": "intermediate"},
            ],
            "projects": [
                {"title": "Real-time Telemetry Data Pipeline", "technologies": ["Kafka", "Spark Streaming", "PostgreSQL"]},
            ],
        },
        "skill_gap_report": {
            "target_role": "Data Engineer",
            "overall_match_percentage": 91.0,
            "strengths": ["Python", "SQL", "Spark", "Database Optimization"],
            "missing_skills": ["Airflow Workflow Orchestration", "dbt"],
        },
        "coding_analytics": {"leetcode_handle": "mohit_patil", "coding_solved": 210, "contest_rating": 1680},
        "matching_result": {
            "readiness_score": {"total": 91.0, "fit_tier": "Highly Prepared"},
            "matches": [
                {
                    "job_id": "microsoft-swe-2026",
                    "company_name": "Microsoft",
                    "job_title": "Data & Applied Scientist",
                    "package_lpa": 27.0,
                    "match_percentage": 92.0,
                    "matched_skills": ["Python", "SQL", "Spark"],
                    "missing_skills": ["CosmosDB"],
                    "confidence": "0.93",
                }
            ],
        },
        "roadmap": {"roadmap_items": []},
        "resume_perfection": {
            "status": "completed",
            "evaluation": {"overall_score": 92, "tier_label": "Verified & Exceptional Match"},
        },
        "metadata": {"student_name": "Mohit Patil", "usn": "01FE23BCI081", "cgpa": 8.70, "generated_at": _now_iso(120)},
    }


def _create_mock_snapshot_bhuwanesh() -> Dict[str, Any]:
    return {
        "student_profile": {
            "name": "Bhuwanesh S",
            "usn": "01FE23BCI049",
            "email": "bhuwanesh.s@kletech.ac.in",
            "education": {
                "degree": "B.Tech Computer Science & Engineering",
                "institution": "KLE Technological University",
                "gpa": 8.60,
                "graduation_year": 2026,
            },
            "skills": [
                {"name": "Linux", "proficiency": "advanced"},
                {"name": "Docker", "proficiency": "advanced"},
                {"name": "Kubernetes", "proficiency": "intermediate"},
                {"name": "CI/CD", "proficiency": "intermediate"},
                {"name": "Python", "proficiency": "intermediate"},
            ],
            "projects": [
                {"title": "Multi-Cluster GitOps Deployment", "technologies": ["Kubernetes", "ArgoCD", "Helm"]},
            ],
        },
        "skill_gap_report": {
            "target_role": "Cloud / DevOps Engineer",
            "overall_match_percentage": 86.0,
            "strengths": ["Kubernetes", "Docker", "Linux System Administration", "CI/CD"],
            "missing_skills": ["Terraform IaC", "Prometheus Alerting"],
        },
        "coding_analytics": {"leetcode_handle": "bhuwanesh_s", "coding_solved": 180, "contest_rating": 1620},
        "matching_result": {
            "readiness_score": {"total": 86.0, "fit_tier": "Highly Prepared"},
            "matches": [
                {
                    "job_id": "cisco-sde-2026",
                    "company_name": "Cisco",
                    "job_title": "Site Reliability & Cloud Engineer",
                    "package_lpa": 19.5,
                    "match_percentage": 89.0,
                    "matched_skills": ["Linux", "Docker", "Kubernetes", "CI/CD"],
                    "missing_skills": ["Go"],
                    "confidence": "0.91",
                }
            ],
        },
        "roadmap": {"roadmap_items": []},
        "resume_perfection": {
            "status": "completed",
            "evaluation": {"overall_score": 86, "tier_label": "Competitive Candidate"},
        },
        "metadata": {"student_name": "Bhuwanesh S", "usn": "01FE23BCI049", "cgpa": 8.60, "generated_at": _now_iso(180)},
    }


def _create_mock_snapshot_rahul() -> Dict[str, Any]:
    return {
        "student_profile": {
            "name": "Rahul K",
            "usn": "01FE23BCI090",
            "email": "rahul.k@kletech.ac.in",
            "education": {
                "degree": "B.Tech Computer Science & Engineering",
                "institution": "KLE Technological University",
                "gpa": 8.55,
                "graduation_year": 2026,
            },
            "skills": [
                {"name": "JavaScript", "proficiency": "advanced"},
                {"name": "TypeScript", "proficiency": "intermediate"},
                {"name": "React.js", "proficiency": "advanced"},
                {"name": "Node.js", "proficiency": "intermediate"},
                {"name": "MongoDB", "proficiency": "intermediate"},
                {"name": "Python", "proficiency": "intermediate"},
            ],
            "projects": [
                {"title": "Real-time Collaborative Canvas", "technologies": ["WebSockets", "React", "Node.js"]},
            ],
        },
        "skill_gap_report": {
            "target_role": "Full-Stack Web Developer",
            "overall_match_percentage": 87.5,
            "strengths": ["React.js", "TypeScript", "REST APIs", "Modern Web Architecture"],
            "missing_skills": ["GraphQL", "Next.js App Router Server Actions"],
        },
        "coding_analytics": {"leetcode_handle": "rahul_k", "coding_solved": 195, "contest_rating": 1640},
        "matching_result": {
            "readiness_score": {"total": 87.5, "fit_tier": "Highly Prepared"},
            "matches": [
                {
                    "job_id": "google-swe-2026",
                    "company_name": "Google",
                    "job_title": "Full Stack Software Engineer",
                    "package_lpa": 32.5,
                    "match_percentage": 87.0,
                    "matched_skills": ["TypeScript", "React.js", "Data Structures"],
                    "missing_skills": ["Go", "C++"],
                    "confidence": "0.90",
                }
            ],
        },
        "roadmap": {"roadmap_items": []},
        "resume_perfection": {
            "status": "completed",
            "evaluation": {"overall_score": 87, "tier_label": "Verified & Exceptional Match"},
        },
        "metadata": {"student_name": "Rahul K", "usn": "01FE23BCI090", "cgpa": 8.55, "generated_at": _now_iso(60)},
    }


# ---------------------------------------------------------------------------
# Mock Store Class
# ---------------------------------------------------------------------------

class MockStore:
    """In-memory store providing automatic mock fallback when DB is unreachable."""

    def __init__(self):
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._decisions: List[Dict[str, Any]] = []
        self._init_defaults()

    def _init_defaults(self):
        # 1. Aditya C (Pending Review)
        self._runs[DEMO_RUN_ID_1] = {
            "id": DEMO_RUN_ID_1,
            "student_id": DEMO_STUDENT_ID_1,
            "status": "pending_review",
            "current_step": "completed",
            "created_at": _now_iso(45),
            "completed_at": _now_iso(30),
            "result_snapshot": _create_mock_snapshot_aditya(),
        }

        # 2. Mohit Patil (Published / Approved)
        self._runs[DEMO_RUN_ID_2] = {
            "id": DEMO_RUN_ID_2,
            "student_id": DEMO_STUDENT_ID_2,
            "status": "published",
            "current_step": "completed",
            "created_at": _now_iso(150),
            "completed_at": _now_iso(120),
            "result_snapshot": _create_mock_snapshot_mohit(),
        }

        # 3. Bhuwanesh S (Published / Approved)
        self._runs[DEMO_RUN_ID_3] = {
            "id": DEMO_RUN_ID_3,
            "student_id": DEMO_STUDENT_ID_3,
            "status": "published",
            "current_step": "completed",
            "created_at": _now_iso(220),
            "completed_at": _now_iso(180),
            "result_snapshot": _create_mock_snapshot_bhuwanesh(),
        }

        # 4. Rahul K (Pending Review)
        self._runs[DEMO_RUN_ID_4] = {
            "id": DEMO_RUN_ID_4,
            "student_id": DEMO_STUDENT_ID_4,
            "status": "pending_review",
            "current_step": "completed",
            "created_at": _now_iso(75),
            "completed_at": _now_iso(60),
            "result_snapshot": _create_mock_snapshot_rahul(),
        }

        # Recent decisions
        self._decisions = [
            {
                "run_id": DEMO_RUN_ID_2,
                "decision": "APPROVED",
                "decided_at": _now_iso(115),
                "comments": "Strong analytical profile and verified database projects. Approved for campus recruitment.",
            },
            {
                "run_id": DEMO_RUN_ID_3,
                "decision": "APPROVED",
                "decided_at": _now_iso(175),
                "comments": "Excellent DevOps hands-on experience and clean portfolio.",
            },
        ]

    # --- Run Management ---

    def save_run(
        self,
        run_id: str,
        student_id: str,
        status: str = "running",
        current_step: str = "init",
        result_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Save or update a run in memory."""
        now = datetime.now(timezone.utc).isoformat()
        if run_id not in self._runs:
            self._runs[run_id] = {
                "id": run_id,
                "student_id": student_id,
                "status": status,
                "current_step": current_step,
                "created_at": now,
                "completed_at": None,
                "result_snapshot": result_snapshot or {},
            }
        else:
            run = self._runs[run_id]
            run["status"] = status
            run["current_step"] = current_step
            if result_snapshot is not None:
                run["result_snapshot"] = result_snapshot
            if status in ("completed", "pending_review", "published"):
                run["completed_at"] = now
        return self._runs[run_id]

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self._runs.get(str(run_id))

    def update_run_status(self, run_id: str, status: str, current_step: Optional[str] = None):
        run = self.get_run(run_id)
        if run:
            run["status"] = status
            if current_step:
                run["current_step"] = current_step
            if status in ("completed", "pending_review", "published"):
                run["completed_at"] = datetime.now(timezone.utc).isoformat()

    # --- Approval Queue & Operations ---

    def get_approval_queue(self) -> Dict[str, Any]:
        """Returns exact payload expected by GET /api/v1/approvals/queue/open."""
        pending = [
            r for r in self._runs.values()
            if r["status"] in ("pending_review", "completed")
        ]
        # Sort newest first
        pending.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        published_count = sum(1 for r in self._runs.values() if r["status"] in ("published", "approved"))
        approved_decisions = sum(1 for d in self._decisions if d["decision"] == "APPROVED")
        rejected_decisions = sum(1 for d in self._decisions if d["decision"] == "REJECTED")
        total_decisions = approved_decisions + rejected_decisions

        approval_rate = round((approved_decisions / max(total_decisions, 1)) * 100, 1) if total_decisions > 0 else 100.0

        return {
            "pending_runs": [
                {
                    "run_id": str(r["id"]),
                    "student_id": str(r["student_id"]),
                    "status": r["status"],
                    "current_step": r["current_step"],
                    "submitted_at": r.get("completed_at") or r.get("created_at"),
                    "created_at": r.get("created_at"),
                    "resume_perfection_score": (
                        (r.get("result_snapshot") or {}).get("resume_perfection", {}).get("evaluation", {}).get("overall_score")
                    ),
                    "resume_perfection_tier": (
                        (r.get("result_snapshot") or {}).get("resume_perfection", {}).get("evaluation", {}).get("tier_label")
                    ),
                }
                for r in pending
            ],
            "recent_decisions": self._decisions[:10],
            "stats": {
                "total_runs": len(self._runs) + 8,  # Include historical baseline count
                "pending_reviews": len(pending),
                "approval_rate_percent": approval_rate,
                "published_versions": published_count + 8,
            },
        }

    def get_run_report(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Returns exact payload for GET /api/v1/approvals/{workflow_run_id}/report."""
        run = self.get_run(run_id)
        if not run:
            # Fallback to Aditya C's snapshot if unknown run_id
            run = self.get_run(DEMO_RUN_ID_1)

        if not run:
            return None

        return {
            "run_id": str(run["id"]),
            "student_id": str(run["student_id"]),
            "status": run["status"],
            "current_step": run["current_step"],
            "result_snapshot": run.get("result_snapshot", {}),
            "created_at": run.get("created_at"),
            "completed_at": run.get("completed_at"),
        }

    def decide_run(self, run_id: str, decision: str, comments: Optional[str] = None) -> Dict[str, Any]:
        """Applies approval/rejection decision in memory."""
        run = self.get_run(run_id)
        if not run:
            # If not found, create ad-hoc run
            run = self.save_run(
                run_id=run_id,
                student_id=str(uuid.uuid4()),
                status="pending_review",
                current_step="completed",
                result_snapshot=_create_mock_snapshot_aditya(),
            )

        new_status = "published" if decision == "approved" else "rejected"
        run["status"] = new_status
        now = datetime.now(timezone.utc).isoformat()

        decision_entry = {
            "run_id": str(run_id),
            "decision": decision.upper(),
            "decided_at": now,
            "comments": comments or (f"Decision marked as {decision} by placement officer."),
        }
        self._decisions.insert(0, decision_entry)

        return {
            "message": f"Run successfully {decision}.",
            "run_id": str(run_id),
            "new_status": new_status,
            "decision": decision,
            "decided_at": now,
        }

    # --- Student Dashboard ---

    def get_student_dashboard(self, run_id: str) -> Dict[str, Any]:
        """Returns exact payload for GET /api/v1/dashboard/student/{run_id}."""
        run = self.get_run(run_id)
        if not run:
            # Default to published Aditya C snapshot for instant live demonstration
            run = self.get_run(DEMO_RUN_ID_1)

        snapshot = (run.get("result_snapshot") or {}) if run else _create_mock_snapshot_aditya()

        # If pending_review and not published, return status
        if run and run.get("status") not in ("published", "approved"):
            return {
                "status": run.get("status", "pending_review"),
                "current_step": run.get("current_step", "completed"),
                "has_approved_plan": False,
                "data": None,
                "resume_perfection": snapshot.get("resume_perfection"),
            }

        # Published snapshot
        student_profile = snapshot.get("student_profile", {})
        skill_gap_report = snapshot.get("skill_gap_report", {})
        coding_analytics = snapshot.get("coding_analytics", {})
        matching_result = snapshot.get("matching_result", {})
        interview_result = snapshot.get("interview_result", {})
        roadmap = snapshot.get("roadmap", {})
        metadata = snapshot.get("metadata", {})

        matches = matching_result.get("matches", [])
        mapped_roadmap = []
        if isinstance(roadmap, dict) and "roadmap_items" in roadmap:
            for i, item in enumerate(roadmap["roadmap_items"]):
                mapped_roadmap.append({
                    "week": item.get("week", i + 1),
                    "skill": item.get("focus_area", "Skill"),
                    "action": item.get("action_item", "Learn"),
                    "resource": item.get("resource", "Online Course"),
                    "estimated_hours": item.get("estimated_hours", 10),
                    "priority": item.get("priority", "high"),
                })

        company_matches = []
        for m in matches:
            company_matches.append({
                "job_id": m.get("job_id"),
                "company": m.get("company_name", "Unknown"),
                "role": m.get("job_title", m.get("role_title", "Software Engineer")),
                "match_score": m.get("match_percentage", 0),
                "confidence": str(m.get("confidence", "0.9")),
                "package_lpa": m.get("package_lpa", 0),
                "matched_skills": m.get("matched_skills", []),
                "missing_skills": m.get("missing_skills", []),
            })

        readiness_score = matching_result.get("readiness_score", {})
        placement_score = readiness_score.get("total", 88.5)

        return {
            "status": "published",
            "has_approved_plan": True,
            "version_number": 1,
            "published_at": run.get("completed_at") or _now_iso(10),
            "data": {
                "student_id": run.get("student_id") if run else DEMO_STUDENT_ID_1,
                "student_name": student_profile.get("name", "Aditya C"),
                "target_domain": matching_result.get("target_domain", "software"),
                "placement_readiness_score": placement_score,
                "score_breakdown": {
                    "technical": readiness_score.get("technical_score", 92.0),
                    "coding": readiness_score.get("coding_score", 85.0),
                    "academic": readiness_score.get("academic_score", 88.5),
                    "fit_tier": readiness_score.get("fit_tier", "Highly Prepared"),
                },
                "student_profile": student_profile,
                "skill_gap_report": skill_gap_report,
                "coding_analytics": coding_analytics,
                "company_matches": company_matches,
                "interview_readiness": interview_result,
                "roadmap": mapped_roadmap,
                "resume_perfection": snapshot.get("resume_perfection"),
                "metadata": metadata,
            },
        }

    def get_default_student_dashboard(self) -> Dict[str, Any]:
        """Returns StudentDashboard object for GET /api/v1/dashboard/me."""
        run = self.get_run(DEMO_RUN_ID_1)
        snap = run.get("result_snapshot", {}) if run else _create_mock_snapshot_aditya()
        return {
            "student_id": DEMO_STUDENT_ID_1,
            "has_approved_plan": True,
            "workflow_status": {
                "run_id": DEMO_RUN_ID_1,
                "status": "published",
                "current_step": "completed",
                "version_number": 1,
                "published_at": _now_iso(15),
            },
            "student_profile": snap.get("student_profile"),
            "skill_gap_report": snap.get("skill_gap_report"),
            "coding_analytics": snap.get("coding_analytics"),
            "matching_result": snap.get("matching_result"),
            "interview_result": snap.get("interview_result"),
            "roadmap": snap.get("roadmap"),
            "resume_perfection": snap.get("resume_perfection"),
        }

    def get_officer_queue_summary(self) -> Dict[str, Any]:
        """Returns OfficerQueueSummary object for GET /api/v1/dashboard/officer/queue."""
        pending = [
            {
                "run_id": str(r["id"]),
                "student_id": str(r["student_id"]),
                "status": r["status"],
                "current_step": r["current_step"],
                "created_at": r.get("created_at"),
            }
            for r in self._runs.values()
            if r["status"] in ("pending_review", "completed")
        ]
        return {
            "pending_review_count": len(pending),
            "recently_approved_count": sum(1 for d in self._decisions if d["decision"] == "APPROVED"),
            "recently_rejected_count": sum(1 for d in self._decisions if d["decision"] == "REJECTED"),
            "pending_runs": pending,
        }

    def get_system_stats(self) -> Dict[str, Any]:
        """Returns SystemStats object for GET /api/v1/admin/stats."""
        total = len(self._runs) + 10
        pending = sum(1 for r in self._runs.values() if r["status"] in ("pending_review", "completed"))
        approved = sum(1 for d in self._decisions if d["decision"] == "APPROVED") + 8
        rejected = sum(1 for d in self._decisions if d["decision"] == "REJECTED") + 1
        published = sum(1 for r in self._runs.values() if r["status"] in ("published", "approved")) + 8
        return {
            "total_workflow_runs": total,
            "pending_review": pending,
            "approved": approved,
            "rejected": rejected,
            "published_versions": published,
        }

    def get_resume_perfection(self, run_id: str) -> Dict[str, Any]:
        """Returns targeted questions and evaluation for resume perfection."""
        run = self.get_run(run_id)
        if not run:
            run = self.get_run(DEMO_RUN_ID_1)

        snap = (run.get("result_snapshot") or {}) if run else _create_mock_snapshot_aditya()
        perfection = snap.get("resume_perfection") or {}

        questions = perfection.get("questions") or [
            {
                "id": "q1",
                "topic": "FastAPI & Agent Architecture",
                "question": "How did you configure background task execution and async streaming in FastAPI?",
                "suggested_answer": "Used Starlette BackgroundTasks and AsyncGenerator with Server-Sent Events.",
            },
            {
                "id": "q2",
                "topic": "Deterministic Matching",
                "question": "Explain the weighted scoring formula used to compute ATS fit score.",
                "suggested_answer": "40% Required Skills, 25% Preferred Skills, 20% Coding Rating, 15% CGPA margin.",
            },
        ]
        evaluation = perfection.get("evaluation") or {
            "overall_score": 88,
            "tier_label": "Verified & Exceptional Match",
            "authenticity_index": 92,
            "evidence_strength": "High",
            "feedback": "Project claims and technical competencies verified against code repositories.",
        }

        return {
            "run_id": str(run_id),
            "status": perfection.get("status", "completed"),
            "questions": questions,
            "evaluation": evaluation,
        }


# Global singleton instance
mock_store = MockStore()
