# Requirements Traceability Matrix

> Placement Readiness & Career Intelligence Portal — Chapter 9 Specification

## Implementation status (2026-10-20)

Each Chapter 9 requirement → where it is implemented → how it is verified. The detailed matrix further down is the original plan; the table here is the current state.

| Chapter 9 | Requirement | Implementation | Verified by | Status |
|-----------|-------------|----------------|-------------|--------|
| §9.2 / §9.3 | Upload resume; link coding + academic accounts with consent **per source** | `POST /consents/me/grant`, `POST /process/upload` (409 without resume consent); `services/consent.py` | `test_gap_fixes.py` consent tests | ✅ |
| §9.4 Resume Agent | Structured profile; validate consent first; flag inconsistent entries | `agents/resume_agent.py`; consent node before parsing; duplicate-resume check | `test_resume_validation.py` | ✅ |
| §9.4 Skill Gap Agent | Approved benchmarks, cite each source, never label "unfit" | `agents/skill_gap_agent.py` + benchmark library; `SKILL_GAP_CITATION` check | `test_pipeline_contract.py` | ✅ |
| §9.4 Coding Analytics | Authorized integrations only; trends not raw submissions | `connectors/coding_connector.py` (consent-checked GitHub/LeetCode) | `test_gap_fixes.py` | ✅ |
| §9.8 | Skill Gap ‖ Coding Analytics in parallel, join before matching | `agents/graph.py` fan-out / `join_parallel` | `test_lab7_smoke.py` | ✅ |
| §9.4 Job Matching | Score + ranked matches with confidence & reasoning; low confidence → human | `agents/job_matching_agent.py` over database drives; `LOW_CONFIDENCE_FLAGGED`; flagged in officer report | `test_gap_fixes.py` | ✅ |
| §9.4 Interview Agent | Mock-interview practice + roadmap; AI feedback marked; recordings private | `agents/interview_agent.py`; `POST /interviews/practice` (answers not stored); roadmap download | `test_gap_fixes.py` (practice) | ✅ |
| §9.4 Convener review | Officer approves / edits / overrides; final authority | `/approvals/{id}/decide`, `/edit`, `/override` (placement_officer only) | `test_gap_fixes.py` | ✅ |
| §9.7 Validation | Gaps cited; eligibility enforced; no application without consent; bias check | `agents/validation_agent.py` (19 checks incl. `ELIGIBILITY_ENFORCED`, `NO_APPLICATION_WITHOUT_CONSENT`, `BIAS_CHECK`) | `test_pipeline_contract.py` | ✅ |
| §9.7 Connector | One governed surface for profiles, requirements, assessments | `connectors/hub.py` | `tests/fakes.py` swap | ✅ |
| §9.9 Dashboard | Score + signals, cited gaps, matches w/ confidence, roadmap + mock plan | Officer console inline report; student dashboard | Browser check | ✅ |
| §9.11 Pilot | Intake form; benchmark library 5–8 roles; coding connector; exportable roadmap | `/onboarding`; 10 seeded roles; coding connector; "Download roadmap" | — | ✅ |
| §9.12 | No release without review; never expose one student's data to another | Only `pending_review` runs reach the queue; chat / evidence / status / versions / preparedness scoped to owner | `test_gap_fixes.py` access tests | ✅ |
| §9.12 | Keep benchmarks and company requirements current | Drives editable by officers; benchmark editor (`/benchmarks`, Placement Cell console tab), audited | `test_benchmarks.py` | ✅ |
| Lab 1 | ≥2 clarifying questions, editable plan, revise on feedback | `POST /planner/clarify` | `test_gap_fixes.py` | ✅ |
| Lab 4 | Tag + similarity retrieval over store and history | KB tag filters + full-text + sentence-embedding re-rank (local model); similar prior students (anonymised) | `test_gap_fixes.py`, `test_semantic_similarity.py` | ✅ |
| Lab 6 | Audit every step; resume from checkpoint after crash | Audit log; SQLite checkpointer; resume on startup and via `/workflows/{id}/resume` | `test_checkpoint_resume.py` | ✅ |
| Lab 8 | Parallel workers + merge by plan alignment | Batch re-run; per-student best-of-N roadmap candidates selected by plan alignment | `test_gap_fixes.py`, `test_checkpoint_resume.py` | ✅ |
| Lab 10 | Diagnose and regenerate only the failing part; escalate | `agents/self_healing.py` | `test_lab10.py` | ✅ |
| Lab 11 | Nothing reaches the officer without a green report | `validation_failed` runs never queued | `test_gap_fixes.py` | ✅ |
| Lab 12 | Officer-only publish; versioned; one-click rollback; confidentiality | `_publish`, `POST /versions/{id}/rollback` (re-validated), server-side logout, admin account control | `test_gap_fixes.py` | ✅ |
| Lab 13 | Role-family specialists with checkable output | `core/domains/specialists.py`, `SPECIALIST_OUTPUT_VALID` | `test_gap_fixes.py` | ✅ |
| Lab 14 | Request → approved, published plan in one session, with dashboard + audit | Student → officer → publish flow; `/admin` audit log | Full suite + browser check | ✅ |

---

## Original planning matrix

## Document Conventions

- **REQ-XX**: Requirement identifier
- **Status**: `PLANNED` | `IN_PROGRESS` | `IMPLEMENTED` | `TESTED` | `VERIFIED`
- Each requirement maps to: Architecture Component → DB Entity → API → Agent/Node → UI Component → Test → Lab

---

## 1. Core Pipeline Requirements

| ID | Requirement | Source | Architecture Component | DB Entities | API Endpoints | Agent/Node | UI Component | Tests | Lab | Status |
|----|-------------|--------|----------------------|-------------|---------------|------------|-------------|-------|-----|--------|
| REQ-01 | Student uploads resume with explicit consent | §9.1, §9.3 | File Upload Service | `resumes`, `consents`, `students` | `POST /api/resumes/upload`, `POST /api/consents` | Resume Agent (A1) | Resume Upload Page | Unit: file validation; Int: upload flow; E2E: consent→upload | L2, L5 | PLANNED |
| REQ-02 | Resume Agent extracts skills, projects, experience into structured profile | §9.3, §9.4 | Resume Parsing Service | `student_profiles`, `skills`, `student_skills`, `projects`, `experiences` | `POST /api/resumes/{id}/parse`, `GET /api/profiles/{id}` | Resume Agent (A1) | Profile View | Unit: parsing accuracy; Int: parse→store | L2, L7 | PLANNED |
| REQ-03 | Skill Gap Agent benchmarks profile against target-role requirements | §9.3, §9.4 | Skill Gap Analysis Service | `skill_gaps`, `role_skills`, `skill_benchmarks` | `POST /api/analysis/skill-gaps`, `GET /api/skill-gaps/{student_id}` | Skill Gap Agent (A2) | Skill Gap Visualization | Unit: gap detection; Int: profile→gap | L7, L9 | PLANNED |
| REQ-04 | Coding Analytics Agent aggregates coding-platform activity | §9.3, §9.4 | Coding Analytics Service | `coding_analytics`, `coding_submissions`, `contest_performances` | `POST /api/analytics/coding`, `GET /api/analytics/{student_id}` | Coding Analytics Agent (A3) | Coding Analytics Dashboard | Unit: aggregation; Int: platform→analytics | L7, L8 | PLANNED |
| REQ-05 | Skill Gap and Coding Analytics run in parallel | §9.8 Table 10 | LangGraph Parallel Node | — | — | Graph parallel branch | — | Int: parallel execution timing | L8 | PLANNED |
| REQ-06 | Job Matching Agent computes placement score and ranks company/role matches | §9.3, §9.4 | Matching & Scoring Engine | `readiness_scores`, `company_matches`, `score_breakdowns` | `POST /api/matching/compute`, `GET /api/matches/{student_id}` | Job Matching Agent (A4) | Company Match List, Readiness Score | Unit: scoring algorithm; Int: gap+analytics→match | L7, L9 | PLANNED |
| REQ-07 | Interview Agent runs mock-interview practice and compiles learning roadmap | §9.3, §9.4 | Interview Service | `interview_sessions`, `interview_questions`, `interview_responses`, `interview_feedback`, `roadmaps` | `POST /api/interviews/start`, `POST /api/interviews/{id}/respond`, `GET /api/roadmaps/{student_id}` | Interview Agent (A5) | Mock Interview UI, Roadmap View | Unit: question generation; Int: mock flow | L7 | PLANNED |
| REQ-08 | Placement Cell reviews, approves/rejects readiness score and roadmap | §9.3, §9.4 | Approval Workflow Service | `approval_decisions`, `workflow_runs` | `POST /api/approvals/{run_id}`, `GET /api/reviews/pending` | Human Gate (A6) | Review Dashboard, Approval Controls | Int: approval workflow; E2E: review→publish | L12 | PLANNED |

---

## 2. Coordinator & Orchestration Requirements

| ID | Requirement | Source | Architecture Component | DB Entities | API Endpoints | Agent/Node | UI Component | Tests | Lab | Status |
|----|-------------|--------|----------------------|-------------|---------------|------------|-------------|-------|-----|--------|
| REQ-09 | Coordinator receives request, creates execution plan, locks before work | §9.7 Table 6 | Coordinator Service (LangGraph) | `workflow_runs`, `execution_plans` | `POST /api/workflows/start` | Coordinator (A0) | Workflow Status | Unit: plan creation; Int: plan→lock | L1, L3 | PLANNED |
| REQ-10 | Coordinator manages run state, checkpoints, budgets | §9.7, §9.10 Lab 6 | Runtime Controller | `workflow_runs`, `agent_executions`, `checkpoints` | `GET /api/workflows/{id}/status` | Coordinator (A0) | Run Monitor | Unit: checkpoint; Int: resume-from-checkpoint | L6 | PLANNED |
| REQ-11 | Coordinator invokes specialist agents in correct graph order | §9.5 Table 4, §9.8 | LangGraph State Machine | `agent_executions` | — | All Agents | Graph Visualization | Int: execution order; E2E: full pipeline | L7 | PLANNED |
| REQ-12 | Coordinator enforces permissions and data scope | §9.4 Table 3 | Auth Middleware + Coordinator | `roles`, `permissions` | — | Coordinator (A0) | — | Unit: permission checks; Sec: unauthorized access | L12 | PLANNED |
| REQ-13 | Coordinator manages retries with bounded count | §9.7, §9.10 Lab 10 | Self-Healing Loop | `validation_reports`, `agent_executions` | — | Coordinator + Validation | Retry Status | Unit: retry budget; Int: failure→retry→pass | L10 | PLANNED |
| REQ-14 | Coordinator writes audit events for every action | §9.10 Lab 6 | Audit Service | `audit_logs` | `GET /api/audit/{run_id}` | Coordinator (A0) | Audit History | Unit: audit creation; Int: action→log | L6 | PLANNED |

---

## 3. Validation Requirements

| ID | Requirement | Source | Architecture Component | DB Entities | API Endpoints | Agent/Node | UI Component | Tests | Lab | Status |
|----|-------------|--------|----------------------|-------------|---------------|------------|-------------|-------|-----|--------|
| REQ-15 | Recommendations cite specific skill gaps | §9.7 Table 7 check 0 | Validation Service | `validation_reports` | `GET /api/validations/{run_id}` | Validation Agent | Validation Report View | Unit: citation check | L10, L11 | PLANNED |
| REQ-16 | Eligibility rules are enforced | §9.7 Table 7 check 1 | Eligibility Engine | `validation_reports` | — | Validation Agent | — | Unit: eligibility rules | L10, L11 | PLANNED |
| REQ-17 | No application submitted without student consent | §9.7 Table 7 check 2 | Consent Validator | `consents`, `validation_reports` | — | Validation Agent | — | Unit: consent check | L10, L12 | PLANNED |
| REQ-18 | Shortlisting checked for bias | §9.7 Table 7 check 3 | Bias Checker | `validation_reports` | — | Validation Agent | — | Unit: bias detection | L10 | PLANNED |
| REQ-19 | Validation failure prevents publication | §9.2, §9.7 | Validation Gate | `validation_reports` | — | Validation Agent | Error State UI | Int: fail→block | L10, L11 | PLANNED |
| REQ-20 | Self-healing: diagnose failure, regenerate only failing component | §9.10 Lab 10 | Targeted Regeneration | `agent_executions`, `validation_reports` | — | Coordinator + Validation | Repair Log | Unit: targeted regen; Fault injection | L10 | PLANNED |

---

## 4. Evidence & Grounding Requirements

| ID | Requirement | Source | Architecture Component | DB Entities | API Endpoints | Agent/Node | UI Component | Tests | Lab | Status |
|----|-------------|--------|----------------------|-------------|---------------|------------|-------------|-------|-----|--------|
| REQ-21 | Every output grounded in verified skills and stated role requirements | §9.10 Lab 9 | Evidence Grounding Service | `evidence_records` | `GET /api/evidence/{item_id}` | Grounding Step | Evidence Panel | Unit: evidence attachment; Int: ungrounded→reject | L9 | PLANNED |
| REQ-22 | Evidence record per unit with source, scope, tags | §9.10 Lab 9 Table 28 | Evidence Model | `evidence_records` | `GET /api/evidence/{id}` | All Agents | Evidence Inspector | Unit: evidence schema | L9 | PLANNED |
| REQ-23 | Ungrounded candidates are rejected | §9.10 Lab 9 | Evidence Validator | `validation_reports` | — | Validation Agent | — | Unit: rejection logic | L9 | PLANNED |

---

## 5. Governance & Approval Requirements

| ID | Requirement | Source | Architecture Component | DB Entities | API Endpoints | Agent/Node | UI Component | Tests | Lab | Status |
|----|-------------|--------|----------------------|-------------|---------------|------------|-------------|-------|-----|--------|
| REQ-24 | Human gate is hard stop — placement officer is final authority | §9.4, §9.12 | Approval Workflow | `approval_decisions` | `POST /api/approvals` | Human Gate (A6) | Approval Controls | E2E: no publish without approval | L12 | PLANNED |
| REQ-25 | Officer can inspect, edit, override, approve, reject, request regeneration | §9.4 Table 3 row 6 | Review Workflow | `approval_decisions`, `versions` | `PUT /api/approvals/{id}`, `POST /api/approvals/{id}/override` | Human Gate (A6) | Review Dashboard | Int: each action | L12 | PLANNED |
| REQ-26 | Versioned publishing with audit trail | §9.7, §9.10 Lab 12 | Versioning Service | `versions`, `audit_logs` | `GET /api/versions/{student_id}` | Governance/Publish | Version History | Int: version creation | L12 | PLANNED |
| REQ-27 | One-click rollback to any approved version | §9.2, §9.10 Lab 12 | Rollback Service | `versions`, `audit_logs` | `POST /api/versions/{id}/rollback` | Governance/Publish | Rollback Button | Int: rollback→restore | L12 | PLANNED |
| REQ-28 | No student-facing result published without approval | §9.12 guardrail 1 | Publication Gate | `approval_decisions` | — | Coordinator | Status Badges | E2E: draft→review→publish flow | L12 | PLANNED |

---

## 6. Security & Privacy Requirements

| ID | Requirement | Source | Architecture Component | DB Entities | API Endpoints | Agent/Node | UI Component | Tests | Lab | Status |
|----|-------------|--------|----------------------|-------------|---------------|------------|-------------|-------|-----|--------|
| REQ-29 | Consent validated before parsing personal data | §9.4, §9.12 | Consent Service | `consents` | `POST /api/consents`, `GET /api/consents/{student_id}` | Resume Agent | Consent Form | Unit: consent check; E2E: no-consent→block | L12 | PLANNED |
| REQ-30 | Never expose one student's data to another | §9.12 guardrail 3 | Data Isolation Layer | — | — | All Agents | — | Sec: cross-student access attempt | L12 | PLANNED |
| REQ-31 | Raw coding submissions kept private | §9.4 Table 3, §9.12 | Privacy Filter | `coding_analytics` | — | Coding Analytics Agent | — | Unit: no raw data exposure | L12 | PLANNED |
| REQ-32 | Role-based access control | §9.10 Lab 12 | RBAC Service | `users`, `roles`, `permissions` | — | Coordinator | — | Unit: role checks; Sec: unauthorized access | L12 | PLANNED |
| REQ-33 | Resume treated as untrusted DATA, not instructions (prompt injection defense) | Master prompt §14 | Input Sanitization | — | — | Resume Agent | — | Sec: injection test | L12 | PLANNED |
| REQ-34 | Secure file upload with validation | Master prompt §13 | File Validation Service | `resumes` | `POST /api/resumes/upload` | Resume Agent | Upload Component | Unit: file type/size validation | L2 | PLANNED |

---

## 7. Connector & Data Access Requirements

| ID | Requirement | Source | Architecture Component | DB Entities | API Endpoints | Agent/Node | UI Component | Tests | Lab | Status |
|----|-------------|--------|----------------------|-------------|---------------|------------|-------------|-------|-----|--------|
| REQ-35 | Single governed connector for all data sources | §9.7 Table 8, §9.10 Lab 5 | Connector Layer | — | — | All Agents | — | Int: connector access; no direct DB | L5 | PLANNED |
| REQ-36 | Connector exposes: student profiles, job/role requirements, skill-assessment results | §9.7 Table 8 | Typed Connector Operations | — | — | Connector | — | Unit: each operation | L5 | PLANNED |
| REQ-37 | No agent touches a data source directly | §9.10 Lab 5 pitfall | Connector Enforcement | — | — | — | — | Arch: no direct DB access in agents | L5 | PLANNED |

---

## 8. Dashboard & UI Requirements

| ID | Requirement | Source | Architecture Component | DB Entities | API Endpoints | Agent/Node | UI Component | Tests | Lab | Status |
|----|-------------|--------|----------------------|-------------|---------------|------------|-------------|-------|-----|--------|
| REQ-38 | Readiness score panel with driving signals | §9.9 Table 11 | Dashboard Service | `readiness_scores`, `score_breakdowns` | `GET /api/dashboard/student/{id}` | — | Readiness Score Card | UI: score display | L14 | PLANNED |
| REQ-39 | Skill gaps panel with cited benchmarks | §9.9 Table 11 | Dashboard Service | `skill_gaps` | `GET /api/dashboard/gaps/{id}` | — | Skill Gap Chart | UI: gap visualization | L14 | PLANNED |
| REQ-40 | Company matching panel with confidence and reasoning | §9.9 Table 11 | Dashboard Service | `company_matches` | `GET /api/dashboard/matches/{id}` | — | Match Cards | UI: confidence indicators | L14 | PLANNED |
| REQ-41 | Learning roadmap panel with mock-interview plan | §9.9 Table 11 | Dashboard Service | `roadmaps` | `GET /api/dashboard/roadmap/{id}` | — | Roadmap Timeline | UI: roadmap display | L14 | PLANNED |
| REQ-42 | Status badges: DRAFT, VALIDATED, PENDING REVIEW, APPROVED, PUBLISHED, REJECTED | Master prompt §12 | Status Management | `workflow_runs` | — | — | Status Badges | UI: each state | L12 | PLANNED |

---

## 9. Scoring & Matching Requirements

| ID | Requirement | Source | Architecture Component | DB Entities | API Endpoints | Agent/Node | UI Component | Tests | Lab | Status |
|----|-------------|--------|----------------------|-------------|---------------|------------|-------------|-------|-----|--------|
| REQ-43 | Transparent scoring with configurable weights | Master prompt §16 | Scoring Engine | `readiness_scores`, `score_breakdowns`, `scoring_configs` | `GET /api/scoring/config`, `PUT /api/scoring/config` | Job Matching Agent | Score Breakdown | Unit: scoring math | L7 | PLANNED |
| REQ-44 | Score exposes contributing factors with breakdown | Master prompt §16 | Score Breakdown Model | `score_breakdowns` | `GET /api/scores/{id}/breakdown` | Job Matching Agent | Breakdown Chart | Unit: factor breakdown | L7 | PLANNED |
| REQ-45 | Confidence and explainable reasoning for matches | §9.4, §9.12 | Explanation Service | `company_matches` | `GET /api/matches/{id}/explanation` | Job Matching Agent | Match Explanation | Unit: explanation gen | L9 | PLANNED |
| REQ-46 | Low-confidence matches routed to human review | §9.4, §9.12 | Confidence Router | `company_matches`, `approval_decisions` | — | Job Matching Agent | Low-Confidence Flag | Unit: routing logic | L10 | PLANNED |

---

## 10. MVP Roadmap Mapping (from §9.11 Table 40)

| MVP Order | Capability | Requirements Covered | Lab Coverage |
|-----------|-----------|---------------------|-------------|
| 1 | Resume parsing | REQ-01, REQ-02, REQ-29, REQ-33, REQ-34 | L1-L6 |
| 2 | Skill gap + coding analytics | REQ-03, REQ-04, REQ-05 | L7, L8 |
| 3 | Placement scoring & matching | REQ-06, REQ-43, REQ-44, REQ-45, REQ-46 | L7, L9 |
| 4 | Interview & roadmap | REQ-07 | L7 |
| 5 | Placement Cell approval | REQ-08, REQ-24, REQ-25, REQ-28 | L12 |
| 6 | Readiness dashboard | REQ-38, REQ-39, REQ-40, REQ-41, REQ-42 | L14 |

---

## 11. Ambiguities & Clarifications Needed

| ID | Area | Ambiguity | Recommendation | Decision |
|----|------|-----------|----------------|----------|
| AMB-01 | Coding Platform Integration | Spec says "coding-platform integrations" but doesn't specify which platforms (LeetCode, HackerRank, Codeforces, etc.) | Support configurable platform connectors; start with mock data simulating LeetCode-like structure | Use mock connector + configurable adapter pattern |
| AMB-02 | Academic Records | "Links academic-record accounts" — no schema or source specified | Model academic records as a structured entity with GPA, courses, grades; ingestible via upload or API | Create an academic_records table + CSV upload |
| AMB-03 | Readiness Score Formula | Score composition mentioned but exact formula not specified | Implement configurable weighted scoring per Master prompt §16 with default weights | Configurable via admin panel |
| AMB-04 | Interview Agent Scope | "Runs mock-interview practice" — unclear if real-time chat, async Q&A, or both | Implement async Q&A mock interview with AI-generated questions and evaluation | Start with async, extensible to real-time |
| AMB-05 | Role-Family Packs (Lab 13) | "Software, core, analytics, higher studies" — no detailed specialization rules | Define role-family-specific question banks, skill taxonomies, and matching rules per family | Create pluggable specialist configurations |
| AMB-06 | Bias Check | "Shortlisting is checked for bias" (Table 7) — no specific bias metrics defined | Implement demographic parity checks and flag statistical anomalies across student cohorts | Use statistical analysis, not demographic data collection |
| AMB-07 | Learning Roadmap Structure | Roadmap mentioned but format not specified | Structured milestones with resources, timelines, priorities linked to skill gaps | Create configurable roadmap templates |
| AMB-08 | Multi-Student Parallel Processing | Lab 8 mentions parallel student processing — unclear if batch or individual triggers | Support both: individual student trigger + batch processing for placement seasons | Individual primary; batch as admin feature |
