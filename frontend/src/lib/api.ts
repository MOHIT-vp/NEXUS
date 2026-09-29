/**
 * API client to communicate with the FastAPI backend.
 * Base URL defaults to http://localhost:8000
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

/**
 * Fetch wrapper — no authentication for MVP.
 */
async function fetchAPI(endpoint: string, options: RequestInit = {}) {
  const headers: Record<string, string> = {
    ...((options.headers as Record<string, string>) || {}),
  };

  // Only set Content-Type for JSON requests (not FormData)
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail: string | undefined;
    try {
      const errorText = await response.text();
      try {
        const errorData = JSON.parse(errorText);
        if (errorData && typeof errorData === "object") {
          if (typeof errorData.detail === "string") {
            errorDetail = errorData.detail;
          } else if (Array.isArray(errorData.detail)) {
            errorDetail = errorData.detail
              .map((e: unknown) => {
                if (typeof e === "string") return e;
                if (e && typeof e === "object") {
                  const errObj = e as Record<string, unknown>;
                  const msg =
                    typeof errObj.msg === "string"
                      ? errObj.msg
                      : typeof errObj.message === "string"
                      ? errObj.message
                      : null;
                  const loc = Array.isArray(errObj.loc)
                    ? errObj.loc.filter((l) => l !== "body").join(".")
                    : null;
                  if (msg && loc) return `${msg} (${loc})`;
                  if (msg) return msg;
                  return JSON.stringify(e);
                }
                return String(e);
              })
              .filter(Boolean)
              .join("; ");
          } else if (errorData.detail && typeof errorData.detail === "object") {
            const detailObj = errorData.detail as Record<string, unknown>;
            if (typeof detailObj.message === "string") {
              errorDetail = detailObj.message;
            } else if (typeof detailObj.error === "string") {
              errorDetail = detailObj.error;
            } else {
              errorDetail = JSON.stringify(errorData.detail);
            }
          } else if (typeof errorData.message === "string") {
            errorDetail = errorData.message;
          } else if (typeof errorData.error === "string") {
            errorDetail = errorData.error;
          }
        }
      } catch {
        if (errorText && errorText.trim().length > 0 && errorText.length < 500) {
          errorDetail = errorText.trim();
        }
      }
    } catch {
      // Ignore read errors
    }

    throw new Error(errorDetail || `API error: ${response.status}`);
  }

  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return null;
  }

  const text = await response.text();
  if (!text || !text.trim()) {
    return null;
  }

  return JSON.parse(text);
}

// ------------------------------------------------------------------
// Process API (Workflow)
// ------------------------------------------------------------------

/** Upload resume and start real LangGraph pipeline. Returns { run_id, status, message }. */
export async function uploadResume(formData: FormData): Promise<{
  run_id: string;
  status: string;
  message: string;
}> {
  return fetchAPI("/api/v1/process/upload", {
    method: "POST",
    body: formData,
  });
}

/** Poll workflow status by run_id. */
export async function getWorkflowStatus(runId: string): Promise<{
  run_id: string;
  status: string;
  current_step: string | null;
  student_id: string | null;
}> {
  return fetchAPI(`/api/v1/process/status/${runId}`);
}

// ------------------------------------------------------------------
// Dashboard API
// ------------------------------------------------------------------

/** Fetch student dashboard by run_id (unauthenticated MVP). */
export async function getDashboardByRunId(runId: string): Promise<Record<string, unknown>> {
  return fetchAPI(`/api/v1/dashboard/student/${runId}`);
}

/** Authenticated student dashboard (for future use with login). */
export async function getStudentDashboard(): Promise<Record<string, unknown>> {
  return fetchAPI("/api/v1/dashboard/me");
}

// ------------------------------------------------------------------
// Officer / Approval API
// ------------------------------------------------------------------

/** Get the approval queue (unauthenticated MVP). */
export async function getApprovalQueue(): Promise<Record<string, unknown>> {
  return fetchAPI("/api/v1/approvals/queue/open");
}

/** Get the full report for a workflow run. */
export async function getRunReport(runId: string): Promise<Record<string, unknown>> {
  return fetchAPI(`/api/v1/approvals/${runId}/report`);
}

/** Submit an approval decision (approve/reject). */
export async function submitDecision(
  runId: string,
  decision: "approved" | "rejected",
  comments?: string
): Promise<Record<string, unknown>> {
  return fetchAPI(`/api/v1/approvals/${runId}/decide`, {
    method: "POST",
    body: JSON.stringify({ decision, comments }),
  });
}

/** Get officer queue with auth (original, for future use). */
export async function getOfficerQueue() {
  return fetchAPI("/api/v1/dashboard/officer/queue");
}

// ------------------------------------------------------------------
// Admin API
// ------------------------------------------------------------------

export async function getSystemStats() {
  return fetchAPI("/api/v1/admin/stats");
}

export async function getDomainConfigs() {
  return fetchAPI("/api/v1/admin/domains");
}

// ------------------------------------------------------------------
// Chat API
// ------------------------------------------------------------------

export async function sendChatMessage(
  message: string,
  history: { role: string; content: string }[],
  runId?: string | null
): Promise<{ response: string }> {
  return fetchAPI("/api/v1/chat", {
    method: "POST",
    body: JSON.stringify({
      message,
      history,
      run_id: runId || null,
    }),
  });
}

// ------------------------------------------------------------------
// Companies & Recruitment Drives API
// ------------------------------------------------------------------

export interface RecruitmentRound {
  round_number: number;
  name: string;
  type: string;
  description?: string;
  duration_minutes?: number;
}

export interface JobDrive {
  job_id: string;
  company_id: string;
  company_name: string;
  industry?: string;
  website?: string;
  location?: string;
  description?: string;
  role_title: string;
  role_family: string;
  package_lpa: number;
  min_cgpa: number;
  max_backlogs?: number;
  min_experience: number;
  required_skills: string[];
  preferred_skills: string[];
  drive_date?: string;
  deadline?: string;
  status: string;
  selection_rounds: RecruitmentRound[];
  created_at?: string;
}

export interface PreparednessCheckResult {
  job_id: string;
  company_name: string;
  role_title: string;
  role_family: string;
  package_lpa: number;
  min_cgpa: number;
  max_backlogs?: number;
  student_cgpa?: number;
  student_backlogs?: number;
  student_coding_solved?: number;
  is_cgpa_eligible?: boolean;
  is_backlog_eligible?: boolean;
  is_fully_eligible?: boolean;
  is_eligible: boolean;
  eligibility_reasons: string[];
  overall_score: number;
  max_score: number;
  match_percentage: number;
  match_tier: string;
  confidence: number;
  breakdown: {
    skill_coverage: { score: number; max: number; percentage: number };
    coding_performance: { score: number; max: number; percentage: number };
    project_relevance: { score: number; max: number; percentage: number };
    interview_readiness: { score: number; max: number; percentage: number };
    academic_eligibility: { score: number; max: number; percentage: number };
  };
  matched_skills: { name: string; type: string; proficiency: string; status: string }[];
  missing_skills: {
    skill: string;
    importance: string;
    severity: string;
    recommendation: string;
    learning_resource: string;
    estimated_hours: number;
  }[];
  fit_highlights: string[];
  concern_areas: string[];
  prep_roadmap: {
    week: number;
    focus_area: string;
    action_item: string;
    resource: string;
    estimated_hours: number;
    priority: string;
  }[];
  selection_rounds: RecruitmentRound[];
}

export interface CohortReadinessResult {
  job_id: string;
  company_name: string;
  role_title: string;
  total_students_evaluated: number;
  eligible_count: number;
  eligible_percentage: number;
  average_readiness_score: number;
  high_fit_count: number;
  moderate_fit_count: number;
  low_fit_count: number;
  common_missing_skills: { skill: string; missing_count: number; missing_percentage: number }[];
}

/** List campus recruitment drives with optional search/filter. */
export async function listRecruitmentDrives(params?: {
  search?: string;
  roleFamily?: string;
  status?: string;
}): Promise<JobDrive[]> {
  const query = new URLSearchParams();
  if (params?.search) query.append("search", params.search);
  if (params?.roleFamily) query.append("role_family", params.roleFamily);
  if (params?.status) query.append("status", params.status);

  const qs = query.toString() ? `?${query.toString()}` : "";
  return fetchAPI(`/api/v1/companies${qs}`);
}

/** Get full details of a specific recruitment drive. */
export async function getRecruitmentDrive(jobId: string): Promise<JobDrive> {
  return fetchAPI(`/api/v1/companies/jobs/${jobId}`);
}

/** Placement Cell lists a new company coming for recruitment. */
export async function createRecruitmentDrive(data: Partial<JobDrive>): Promise<JobDrive> {
  return fetchAPI("/api/v1/companies", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** Placement Cell updates a recruitment drive. */
export async function updateRecruitmentDrive(jobId: string, data: Partial<JobDrive>): Promise<JobDrive> {
  return fetchAPI(`/api/v1/companies/jobs/${jobId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

/** Placement Cell deletes/delists a recruitment drive. */
export async function deleteRecruitmentDrive(jobId: string): Promise<void> {
  return fetchAPI(`/api/v1/companies/jobs/${jobId}`, {
    method: "DELETE",
  });
}

/** Student checks their preparedness and skill match with a company's requirements. */
export async function checkCompanyPreparedness(
  jobId: string,
  payload?: {
    run_id?: string;
    student_id?: string;
    skills?: string[];
    cgpa?: number;
    backlogs?: number;
    coding_solved?: number;
    projects?: Record<string, unknown>[];
  }
): Promise<PreparednessCheckResult> {
  return fetchAPI(`/api/v1/companies/jobs/${jobId}/check-preparedness`, {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
}

/** Placement Cell views aggregated cohort readiness for a company. */
export async function getCohortReadiness(jobId: string): Promise<CohortReadinessResult> {
  return fetchAPI(`/api/v1/companies/jobs/${jobId}/cohort-readiness`);
}

// ------------------------------------------------------------------
// Resumes & Duplicate Verification API
// ------------------------------------------------------------------

export interface ResumeVerificationResult {
  is_duplicate: boolean;
  confidence: string;
  similarity_score: number;
  matched_resume_id?: string | null;
  matched_student_id?: string | null;
  matched_student_name?: string | null;
  matched_file_name?: string | null;
  metrics: Record<string, number>;
  reasons: string[];
  matching_snippets: string[];
  status: string;
}

export interface ResumeDetail {
  id: string;
  student_id: string;
  file_name: string;
  file_size: number;
  mime_type: string;
  file_hash?: string | null;
  status: string;
  uploaded_at?: string | null;
  parsed_at?: string | null;
}

/** Verify uniqueness of an uploaded resume against other students' resumes. */
export async function verifyResumeUniqueness(resumeId: string): Promise<ResumeVerificationResult> {
  return fetchAPI(`/api/v1/resumes/${resumeId}/verify`, {
    method: "POST",
  });
}

/** List all resumes for the authenticated student. */
export async function listStudentResumes(): Promise<ResumeDetail[]> {
  return fetchAPI("/api/v1/resumes");
}

/** Get details and validation status for a specific resume. */
export async function getResumeDetail(resumeId: string): Promise<ResumeDetail> {
  return fetchAPI(`/api/v1/resumes/${resumeId}`);
}

// ------------------------------------------------------------------
// Coding Practice API
// ------------------------------------------------------------------

export interface CodingExample {
  input: string;
  output: string;
  explanation: string;
}

export interface CodingProblem {
  id: string;
  title: string;
  difficulty: string;
  description: string;
  constraints?: string[];
  examples: CodingExample[];
  function_name: string;
  starter_code: string;
  test_count: number;
}

export interface TestCaseResult {
  test_case: number;
  input?: Record<string, unknown>;
  passed: boolean;
  expected: unknown;
  actual: unknown;
  error: string | null;
  execution_time_ms?: number;
  console_output?: string;
}

export interface SubmissionResult {
  problem_id: string;
  run_mode?: "run" | "submit";
  all_passed: boolean;
  passed_count: number;
  total_count: number;
  total_execution_time_ms?: number;
  results: TestCaseResult[];
}

/** Fetch all coding practice problems. */
export async function listCodingProblems(): Promise<CodingProblem[]> {
  return fetchAPI("/api/v1/coding/problems");
}

/** Fetch a single coding problem by id. */
export async function getCodingProblem(problemId: string): Promise<CodingProblem> {
  return fetchAPI(`/api/v1/coding/problems/${problemId}`);
}

/** Submit code for a coding problem and get test results (all test cases). */
export async function submitCodingSolution(
  problemId: string,
  code: string,
  mode: "run" | "submit" = "submit"
): Promise<SubmissionResult> {
  return fetchAPI(`/api/v1/coding/problems/${problemId}/submit`, {
    method: "POST",
    body: JSON.stringify({ code, mode }),
  });
}

/** Run code on sample test cases only (fast feedback). */
export async function runCodingSolution(
  problemId: string,
  code: string
): Promise<SubmissionResult> {
  return fetchAPI(`/api/v1/coding/problems/${problemId}/run`, {
    method: "POST",
    body: JSON.stringify({ code, mode: "run" }),
  });
}

/** Execute code using the unified execute endpoint. */
export async function executeCodingCode(
  problemId: string,
  code: string,
  mode: "run" | "submit" = "submit"
): Promise<SubmissionResult> {
  return fetchAPI("/api/v1/coding/execute", {
    method: "POST",
    body: JSON.stringify({ problem_id: problemId, code, mode }),
  });
}

// ------------------------------------------------------------------
// Resume Perfection & Authenticity Verification API
// ------------------------------------------------------------------

export interface ResumePerfectionQuestion {
  id: string;
  category: string;
  category_label: string;
  target_claim: string;
  question: string;
  context: string;
  options: string[];
  correct_option_index?: number;
  explanation?: string;
  difficulty?: string;
}

export interface StudentAnswerItem {
  question_id: string;
  selected_option_index: number;
  student_notes?: string;
}

export interface QuestionEvaluationResult {
  question_id: string;
  question: string;
  target_claim: string;
  category: string;
  category_label: string;
  selected_option_index: number;
  correct_option_index: number;
  is_correct: boolean;
  score: number;
  selected_text: string;
  correct_text: string;
  explanation: string;
  feedback: string;
  interview_tip: string;
}

export interface CategoryScore {
  category: string;
  category_label: string;
  total_questions: number;
  correct_questions: number;
  score_percentage: number;
}

export interface ResumePerfectionEvaluation {
  overall_score: number;
  total_questions: number;
  correct_count: number;
  perfection_tier: "exceptional" | "proficient" | "surface" | "inconsistent" | string;
  tier_label: string;
  tier_color: string;
  summary: string;
  evaluated_at: string;
  category_breakdown: CategoryScore[];
  question_results: QuestionEvaluationResult[];
  recommendations: string[];
}

export interface ResumePerfectionData {
  run_id: string;
  status: string;
  questions: ResumePerfectionQuestion[];
  evaluation?: ResumePerfectionEvaluation | null;
}

/** Get targeted resume verification questions and existing evaluation for a run. */
export async function getResumePerfection(runId: string): Promise<ResumePerfectionData> {
  return fetchAPI(`/api/v1/process/runs/${runId}/resume-perfection`);
}

/** Submit answers to evaluate perfection with own resume. */
export async function submitResumePerfection(
  runId: string,
  answers: StudentAnswerItem[]
): Promise<{ run_id: string; status: string; evaluation: ResumePerfectionEvaluation }> {
  return fetchAPI(`/api/v1/process/runs/${runId}/resume-perfection/submit`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}

/** Regenerate fresh resume perfection questions for re-testing. */
export async function regenerateResumePerfection(
  runId: string
): Promise<{ run_id: string; status: string; questions: ResumePerfectionQuestion[] }> {
  return fetchAPI(`/api/v1/process/runs/${runId}/resume-perfection/regenerate`, {
    method: "POST",
  });
}

