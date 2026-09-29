# API Design — Placement Readiness & Career Intelligence Portal

## 1. API Conventions

- **Base URL**: `/api/v1`
- **Format**: JSON (application/json)
- **Auth**: Bearer JWT in Authorization header
- **Pagination**: `?page=1&page_size=20` (default 20, max 100)
- **Filtering**: Query params per endpoint
- **Errors**: Consistent `{detail: string, code: string, errors?: []}` format
- **OpenAPI**: Auto-generated via FastAPI at `/docs`

---

## 2. Authentication & Authorization

### POST /api/v1/auth/register
Register a new user.
```
Request:  { email, password, full_name, role }
Response: { id, email, full_name, role, token }
```

### POST /api/v1/auth/login
Authenticate and receive JWT.
```
Request:  { email, password }
Response: { access_token, refresh_token, token_type, expires_in, user: {...} }
```

### POST /api/v1/auth/refresh
Refresh access token.
```
Request:  { refresh_token }
Response: { access_token, expires_in }
```

### GET /api/v1/auth/me
Get current user profile. **Auth**: Any authenticated user.

---

## 3. Student Profile

### GET /api/v1/students/profile
Get current student's profile. **Auth**: Student.

### PUT /api/v1/students/profile
Update student profile (enrollment, department, etc.). **Auth**: Student.

### GET /api/v1/students/{student_id}/profile
Get a specific student's profile. **Auth**: Officer, Faculty, Admin.

### GET /api/v1/students
List all students (with pagination/filters). **Auth**: Officer, Admin.
```
Query: ?department=CSE&semester=8&page=1&page_size=20
```

---

## 4. Consent Management

### GET /api/v1/consents
Get current student's consent statuses. **Auth**: Student.

### POST /api/v1/consents
Grant or update consent. **Auth**: Student.
```
Request:  { consent_type: "resume_processing", granted: true }
Response: { id, consent_type, granted, granted_at }
```

### DELETE /api/v1/consents/{consent_type}
Revoke a specific consent. **Auth**: Student.

---

## 5. Resume Management

### POST /api/v1/resumes/upload
Upload a resume file. **Auth**: Student.
```
Request:  multipart/form-data { file: File }
Response: { id, file_name, status: "uploaded", uploaded_at }
Validation: PDF/DOCX only, max 5MB, file type verification
```

### GET /api/v1/resumes
List student's resumes. **Auth**: Student (own), Officer (any).

### GET /api/v1/resumes/{resume_id}
Get resume details. **Auth**: Student (own), Officer.

### POST /api/v1/resumes/{resume_id}/parse
Trigger resume parsing (starts agent workflow). **Auth**: Student.
```
Precondition: resume_processing consent must be granted
Response: { workflow_run_id, status: "processing" }
```

### GET /api/v1/resumes/{resume_id}/parsed
Get parsed resume data (structured profile). **Auth**: Student (own), Officer.

---

## 6. Target Roles & Role Requirements

### GET /api/v1/roles
List available target roles/jobs. **Auth**: Any authenticated.
```
Query: ?role_family=software&company_id=xxx&page=1
Response: { items: [{ id, title, company, role_family, requirements }], total, page }
```

### GET /api/v1/roles/{job_id}
Get role details with skill requirements. **Auth**: Any authenticated.

### POST /api/v1/roles
Create a new role. **Auth**: Admin, Officer.

### PUT /api/v1/roles/{job_id}
Update role. **Auth**: Admin, Officer.

### GET /api/v1/roles/{job_id}/requirements
Get detailed skill requirements for a role. **Auth**: Any authenticated.

---

## 7. Companies & Campus Recruitment Drives

### GET /api/v1/companies
List recruitment drives and companies with search and filtering. **Auth**: Any authenticated.
```
Query: ?search=tech&domain=AI/ML&page=1
```

### GET /api/v1/companies/jobs/{job_id}
Get specific recruitment drive details. **Auth**: Any authenticated.

### POST /api/v1/companies
List a new recruitment drive / company. **Auth**: Admin, Officer.
```
Request: {
  company_name, role_title, domain, ctc_lpa, min_cgpa, max_backlogs,
  required_skills, preferred_skills, drive_date, location, rounds
}
```

### PUT /api/v1/companies/jobs/{job_id}
Update a recruitment drive. **Auth**: Admin, Officer.

### DELETE /api/v1/companies/jobs/{job_id}
Delete/archive a recruitment drive. **Auth**: Admin, Officer.

### POST /api/v1/companies/jobs/{job_id}/check-preparedness
Evaluate student preparedness and skill match against company requirements. **Auth**: Student, Officer.
```
Request: {
  student_id, student_skills, coding_score, project_score, interview_score, cgpa, backlogs
}
Response: {
  overall_score, match_tier, is_cgpa_eligible, is_backlog_eligible, is_fully_eligible,
  component_scores, matched_skills, missing_skills, recommendations, roadmap_2_week
}
```

### GET /api/v1/companies/jobs/{job_id}/cohort-readiness
Compute cohort-wide readiness analytics across all registered students. **Auth**: Officer, Admin.
```
Response: {
  total_candidates, eligible_candidates, eligibility_rate,
  high_match_count, medium_match_count, low_match_count,
  top_missing_skills: [{ skill, missing_count, percentage }]
}
```

---

## 8. Skill Gap Analysis

### POST /api/v1/analysis/skill-gaps
Trigger skill gap analysis for a student against a target role.
**Auth**: Student (own profile), Officer (any student).
```
Request:  { student_id?, target_job_id }
Response: { workflow_run_id, status: "processing" }
```

### GET /api/v1/analysis/skill-gaps/{student_id}
Get skill gap report for a student. **Auth**: Student (own), Officer.
```
Response: { report_id, target_role, overall_coverage, gaps: [...], strengths: [...] }
```

---

## 9. Coding Analytics

### POST /api/v1/analytics/coding
Trigger coding analytics aggregation. **Auth**: Student (own).
```
Request:  { platform: "leetcode", ... }
Precondition: coding_platform consent granted
Response: { id, status: "processing" }
```

### GET /api/v1/analytics/coding/{student_id}
Get coding analytics. **Auth**: Student (own), Officer.
```
Response: { total_solved, difficulty_dist, topic_stats, trends, contest_rating }
```

---

## 10. Readiness Scoring & Matching

### POST /api/v1/matching/compute
Trigger full matching + scoring pipeline. **Auth**: Student, Officer.
```
Request:  { student_id?, target_roles: [job_id, ...] }
Response: { workflow_run_id, status: "processing" }
```

### GET /api/v1/matching/scores/{student_id}
Get readiness score with breakdown. **Auth**: Student (own), Officer.
```
Response: {
  total_score, max_score, status,
  breakdown: [
    { component: "skill_coverage", points: 34, max: 40, weight: 0.4, weighted: 13.6 },
    ...
  ]
}
```

### GET /api/v1/matching/companies/{student_id}
Get ranked company matches. **Auth**: Student (own, only if published), Officer.
```
Response: {
  matches: [
    { rank, company, job, match_score, confidence, reasoning, is_eligible, evidence_id },
    ...
  ]
}
```

### GET /api/v1/matching/companies/{match_id}/explanation
Get detailed match explanation with evidence. **Auth**: Student (own), Officer.

---

## 11. Interview & Roadmap

### POST /api/v1/interviews/start
Start a mock interview session. **Auth**: Student.
```
Request:  { target_role, session_type: "technical" }
Response: { session_id, first_question: {...} }
```

### POST /api/v1/interviews/{session_id}/respond
Submit a response to an interview question. **Auth**: Student (own session).
```
Request:  { question_id, response_text }
Response: { feedback, score, next_question?: {...} }
```

### GET /api/v1/interviews/{session_id}
Get interview session details and results. **Auth**: Student (own), Officer.

### GET /api/v1/interviews/history/{student_id}
Get interview history. **Auth**: Student (own), Officer.

### GET /api/v1/roadmaps/{student_id}
Get learning roadmap. **Auth**: Student (own, if published), Officer.
```
Response: { items: [{ title, skill, priority, resources, estimated_hours, is_completed }] }
```

### PATCH /api/v1/roadmaps/{roadmap_id}/items/{item_id}
Update roadmap item progress. **Auth**: Student (own).

---

## 12. Workflow Management

### POST /api/v1/workflows/start
Start a full placement readiness workflow. **Auth**: Student, Officer.
```
Request:  { student_id, target_roles: [job_id, ...] }
Response: { run_id, status: "pending" }
```

### GET /api/v1/workflows/{run_id}
Get workflow run status and details. **Auth**: Initiator, Officer.
```
Response: {
  run_id, status, current_step, retry_count,
  agent_executions: [...],
  validation_report: {...},
  started_at, ...
}
```

### GET /api/v1/workflows
List workflow runs. **Auth**: Student (own), Officer (all).
```
Query: ?student_id=xxx&status=awaiting_review&page=1
```

---

## 13. Validation

### GET /api/v1/validations/{run_id}
Get validation report for a workflow run. **Auth**: Officer.
```
Response: {
  passed, total_checks, passed_checks, failed_checks,
  checks: [{ check_name, check_code, passed, message, severity }],
  diagnosis
}
```

---

## 14. Approval & Review

### GET /api/v1/reviews/pending
Get pending reviews for current officer. **Auth**: Officer, Faculty.
```
Query: ?page=1&page_size=20
Response: { items: [{ run_id, student, readiness_score, status, submitted_at }], total }
```

### GET /api/v1/reviews/{run_id}
Get full review details (score, gaps, matches, evidence, validation). **Auth**: Officer.

### POST /api/v1/approvals
Submit an approval decision. **Auth**: Officer, Faculty.
```
Request:  {
  workflow_run_id,
  decision: "approved" | "rejected" | "request_changes",
  comments?,
  edits?: { score_override?, match_edits?: [...] }
}
Response: { id, decision, reviewed_at }
```

---

## 15. Publishing & Versioning

### GET /api/v1/versions/{student_id}
Get version history. **Auth**: Student (own), Officer.
```
Response: { versions: [{ version_number, status, approved_by, published_at }] }
```

### GET /api/v1/versions/{student_id}/{version_number}
Get a specific version snapshot. **Auth**: Student (own), Officer.

### POST /api/v1/versions/{version_id}/rollback
Rollback to a specific approved version. **Auth**: Officer.
```
Response: { new_version_number, status: "published", rolled_back_from }
```

---

## 16. Audit History

### GET /api/v1/audit/{run_id}
Get audit trail for a workflow run. **Auth**: Officer, Admin.
```
Response: { events: [{ timestamp, actor, action, agent, decision, details }] }
```

### GET /api/v1/audit/student/{student_id}
Get all audit events for a student. **Auth**: Officer, Admin.
```
Query: ?action=approval&page=1
```

---

## 17. Admin / Configuration

### GET /api/v1/admin/scoring-config
Get current scoring configuration. **Auth**: Admin.

### PUT /api/v1/admin/scoring-config
Update scoring weights. **Auth**: Admin.
```
Request:  { skill_coverage: { weight: 0.4, max: 40 }, coding: { weight: 0.25, max: 25 }, ... }
```

### GET /api/v1/admin/skills
Manage skill taxonomy. **Auth**: Admin.

### POST /api/v1/admin/skills
Add a new skill to taxonomy. **Auth**: Admin.

### GET /api/v1/admin/benchmarks
Manage skill benchmarks. **Auth**: Admin.

### PUT /api/v1/admin/benchmarks/{id}
Update a benchmark. **Auth**: Admin.

### GET /api/v1/admin/system/health
Health check. **Auth**: None.

---

## 18. Dashboard Aggregation

### GET /api/v1/dashboard/student/{student_id}
Get complete student dashboard data. **Auth**: Student (own), Officer.
```
Response: {
  profile, readiness_score, score_breakdown,
  skill_gaps, company_matches, roadmap,
  interview_history, status, version
}
```

### GET /api/v1/dashboard/officer
Get officer overview dashboard. **Auth**: Officer.
```
Response: {
  pending_reviews, total_students, approved_today,
  avg_readiness_score, low_confidence_count,
  recent_activity
}
```

---

## 19. Error Response Format

All errors follow:
```json
{
  "detail": "Human-readable message",
  "code": "ERROR_CODE",
  "errors": [
    { "field": "email", "message": "Invalid email format" }
  ]
}
```

Standard HTTP codes: 200, 201, 400, 401, 403, 404, 409, 422, 429, 500
