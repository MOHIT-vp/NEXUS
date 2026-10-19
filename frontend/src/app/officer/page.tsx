"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getApprovalQueue,
  submitDecision,
  editRun,
  overrideRun,
  rollbackVersion,
  getRunReport,
  getSessionUser,
  signOut,
  listRecruitmentDrives,
  deleteRecruitmentDrive,
  JobDrive,
} from "@/lib/api";
import {
  Users,
  CheckCircle,
  XCircle,
  Clock,
  BarChart3,
  ArrowLeft,
  FileSearch,
  Loader2,
  Building2,
  Plus,
  Trash2,
  Search,
  Calendar,
  DollarSign,
  GraduationCap,
} from "lucide-react";
import Link from "next/link";
import { PBBadge } from "@/components/ui/pb-badge";
import { PBButton } from "@/components/ui/pb-button";
import { Loader } from "@/components/ui/loader";
import { CreateDriveModal } from "@/components/companies/create-drive-modal";
import { CohortAnalyticsModal } from "@/components/companies/cohort-analytics-modal";
import { RunReport } from "@/components/officer/run-report";
import { BenchmarkEditor } from "@/components/officer/benchmark-editor";

export default function OfficerDashboardPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"evaluations" | "drives" | "benchmarks">("evaluations");
  // Per-run edit / override panel
  const [openPanel, setOpenPanel] = useState<{ runId: string; kind: "edit" | "override" | "report" } | null>(null);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [note, setNote] = useState("");
  const [gapSkill, setGapSkill] = useState("");
  const [gapText, setGapText] = useState("");
  const [reason, setReason] = useState("");
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);

  // Evaluations queue state
  const [queueData, setQueueData] = useState<any>(null);
  const [statsData, setStatsData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Recruitment drives state
  const [drives, setDrives] = useState<JobDrive[]>([]);
  const [drivesLoading, setDrivesLoading] = useState(false);
  const [driveSearch, setDriveSearch] = useState("");
  const [roleFamilyFilter, setRoleFamilyFilter] = useState("all");
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedCohortJob, setSelectedCohortJob] = useState<JobDrive | null>(null);
  const [isCohortModalOpen, setIsCohortModalOpen] = useState(false);

  const loadEvaluationsData = async () => {
    try {
      const queue = await getApprovalQueue();
      setQueueData(queue);
      setStatsData(queue.stats);
      setLoading(false);
    } catch (err) {
      console.error("Failed to load officer queue:", err);
      setLoading(false);
    }
  };

  const loadDrives = async () => {
    setDrivesLoading(true);
    try {
      const driveList = await listRecruitmentDrives({
        search: driveSearch || undefined,
        roleFamily: roleFamilyFilter !== "all" ? roleFamilyFilter : undefined,
      });
      setDrives(driveList);
    } catch (err) {
      console.error("Failed to load recruitment drives:", err);
    } finally {
      setDrivesLoading(false);
    }
  };

  useEffect(() => {
    // Only Placement Cell staff can use this console (the server enforces it too)
    const user = getSessionUser();
    if (!user || user.role !== "placement_officer") {
      router.replace("/login?next=/officer");
      return;
    }
    loadEvaluationsData();
    loadDrives();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (activeTab === "drives") {
      loadDrives();
    }
  }, [driveSearch, roleFamilyFilter, activeTab]);

  const handleDecide = async (runId: string, decision: "approved" | "rejected") => {
    setActionLoading(runId);
    setNotice(null);
    try {
      await submitDecision(runId, decision);
      setNotice({ ok: true, text: decision === "approved" ? "Plan approved and published." : "Plan rejected." });
      await loadEvaluationsData();
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : "Failed to submit decision." });
    } finally {
      setActionLoading(null);
    }
  };

  const runAction = async (runId: string, fn: () => Promise<unknown>, success: string) => {
    setActionLoading(runId);
    setNotice(null);
    try {
      await fn();
      setNotice({ ok: true, text: success });
      setOpenPanel(null);
      setNote(""); setGapSkill(""); setGapText(""); setReason("");
      await loadEvaluationsData();
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : "Action failed." });
    } finally {
      setActionLoading(null);
    }
  };

  const handleEdit = (runId: string) => runAction(runId, async () => {
    const res = await editRun(runId, {
      officer_note: note.trim() || undefined,
      gap_recommendations: gapSkill && gapText.trim() ? { [gapSkill]: gapText.trim() } : undefined,
    });
    if (!res.validation_passed) {
      throw new Error(`Saved, but the edited plan failed validation (${res.failing_checks.join(", ")}) and left the queue.`);
    }
  }, "Edit saved and re-validated.");

  const toggleReport = async (runId: string) => {
    if (openPanel?.runId === runId && openPanel?.kind === "report") {
      setOpenPanel(null);
      return;
    }
    setReport(null);
    setOpenPanel({ runId, kind: "report" });
    try {
      setReport(await getRunReport(runId));
    } catch (err) {
      setOpenPanel(null);
      setNotice({ ok: false, text: err instanceof Error ? err.message : "Could not load the report." });
    }
  };

  const handleOverride = (runId: string) =>
    runAction(runId, () => overrideRun(runId, reason.trim()), "Override recorded and plan published.");

  const handleRollback = (versionId: string) => {
    if (!confirm("Roll this student's plan back to the previous version?")) return;
    runAction(versionId, () => rollbackVersion(versionId), "Plan rolled back to the previous version.");
  };

  const handleDeleteDrive = async (jobId: string, companyName: string) => {
    if (!confirm(`Are you sure you want to remove the recruitment drive for ${companyName}?`)) {
      return;
    }
    try {
      await deleteRecruitmentDrive(jobId);
      setDrives(drives.filter(d => d.job_id !== jobId));
    } catch (err) {
      console.error("Failed to delete drive:", err);
      alert("Failed to delete drive. Check console.");
    }
  };

  const handleDriveCreated = (newDrive: JobDrive) => {
    setDrives([newDrive, ...drives]);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-ivory">
        <div className="flex flex-col items-center gap-12 mt-10">
          <Loader />
          <p className="text-sm text-bronze-dark/50 font-medium">Loading officer console...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-ivory">
      {/* Header */}
      <header className="border-b border-border-subtle bg-surface/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 py-5 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Link href="/" className="flex items-center gap-2">
                <span className="text-2xl font-semibold text-charcoal font-stardom">NEXUS</span>
              </Link>
              <span className="text-bronze-dark/30 mx-1">·</span>
              <PBBadge variant="medium">Placement Officer Console</PBBadge>
            </div>
            <h1 className="type-h2">Placement Intelligence & Recruitment Hub</h1>
            <p className="type-body text-bronze-dark/50 mt-1">
              List recruitment drives, evaluate candidate readiness, and publish student plans.
            </p>
          </div>
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="text-sm font-medium text-bronze-dark/60 hover:text-charcoal transition-colors flex items-center gap-1.5"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back to Portal
            </Link>
            <button
              onClick={() => { signOut(); router.push("/login"); }}
              className="text-sm font-medium text-bronze-dark/60 hover:text-charcoal transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>

        {/* Tab switcher */}
        <div className="max-w-7xl mx-auto px-6 lg:px-8 flex gap-8 border-t border-border-subtle/50 text-sm font-semibold">
          <button
            onClick={() => setActiveTab("evaluations")}
            className={`py-3 border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "evaluations"
                ? "border-orange text-orange font-bold"
                : "border-transparent text-bronze-dark/60 hover:text-charcoal"
            }`}
          >
            <Clock className="w-4 h-4" />
            Evaluation Queue
            {queueData?.pending_runs?.length > 0 && (
              <span className="px-2 py-0.5 text-xs rounded-full bg-warning-light text-warning font-bold">
                {queueData.pending_runs.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab("drives")}
            className={`py-3 border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "drives"
                ? "border-orange text-orange font-bold"
                : "border-transparent text-bronze-dark/60 hover:text-charcoal"
            }`}
          >
            <Building2 className="w-4 h-4" />
            Recruitment Drives
            <span className="px-2 py-0.5 text-xs rounded-full bg-surface-muted text-charcoal font-bold">
              {drives.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab("benchmarks")}
            className={`py-3 border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "benchmarks"
                ? "border-orange text-orange font-bold"
                : "border-transparent text-bronze-dark/60 hover:text-charcoal"
            }`}
          >
            <GraduationCap className="w-4 h-4" />
            Skill Benchmarks
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-8 animate-fade-in">
        {/* ════════════════════════════════════════════════════════════
            TAB 1: EVALUATION QUEUE
        ════════════════════════════════════════════════════════════ */}
        {activeTab === "evaluations" && (
          <div className="space-y-8 animate-fade-in">
            {/* KPI Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="surface-card p-5">
                <div className="flex items-center gap-2 mb-2">
                  <BarChart3 className="w-4 h-4 text-bronze-dark/40" />
                  <span className="type-micro">Total Evaluations</span>
                </div>
                <span className="text-3xl font-bold text-charcoal">{statsData?.total_runs || 0}</span>
              </div>
              <div className="surface-card p-5 border-t-2 border-t-warning/40">
                <div className="flex items-center gap-2 mb-2">
                  <Clock className="w-4 h-4 text-warning" />
                  <span className="type-micro">Pending Review</span>
                </div>
                <span className="text-3xl font-bold text-warning">{statsData?.pending_reviews || 0}</span>
              </div>
              <div className="surface-card p-5 border-t-2 border-t-success/40">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle className="w-4 h-4 text-success" />
                  <span className="type-micro">Approval Rate</span>
                </div>
                <span className="text-3xl font-bold text-success">{statsData?.approval_rate_percent || 0}%</span>
              </div>
              <div className="surface-card p-5">
                <div className="flex items-center gap-2 mb-2">
                  <Users className="w-4 h-4 text-bronze-dark/40" />
                  <span className="type-micro">Published Plans</span>
                </div>
                <span className="text-3xl font-bold text-charcoal">{statsData?.published_versions || 0}</span>
              </div>
            </div>

            {notice && (
              <div className={`mb-4 text-sm p-3 rounded-[10px] border font-medium ${notice.ok ? "bg-success-light text-success border-success/20" : "bg-danger-light text-danger border-danger/15"}`}>
                {notice.text}
              </div>
            )}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Pending Queue */}
              <div className="lg:col-span-2 space-y-4">
                <h2 className="type-h3">Pending Student Evaluations</h2>

                {queueData.pending_runs.length === 0 ? (
                  <div className="surface-card p-12 text-center">
                    <div className="w-14 h-14 rounded-[14px] bg-surface-muted flex items-center justify-center mx-auto mb-4">
                      <FileSearch className="w-6 h-6 text-bronze-dark/30" />
                    </div>
                    <p className="font-semibold text-charcoal mb-1">No evaluations waiting for review.</p>
                    <p className="text-sm text-bronze-dark/40">New student submissions will appear here automatically.</p>
                  </div>
                ) : (
                  <div className="surface-card divide-y divide-border-subtle">
                    {queueData.pending_runs.map((run: any) => (
                      <div
                        key={run.run_id}
                        className="p-5 flex flex-col sm:flex-row sm:flex-wrap sm:items-center justify-between gap-4 hover:bg-surface-warm/50 transition-colors"
                      >
                        <div>
                          <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <span className="font-semibold text-charcoal">{run.student_name || run.student_id}</span>
                            {run.target_roles?.length > 0 && (
                              <span className="text-[11px] text-bronze-dark/60">{run.target_roles.join(", ")}</span>
                            )}
                            {run.warnings?.length > 0 && (
                              <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-warning-light text-warning border border-warning/20">
                                Needs override: {run.warnings.join(", ").replace(/_/g, " ").toLowerCase()}
                              </span>
                            )}
                            <PBBadge variant="high">
                              <Clock className="w-3 h-3 mr-1" />
                              {run.status.replace("_", " ")}
                            </PBBadge>
                            {run.resume_perfection_score !== undefined && run.resume_perfection_score !== null ? (
                              <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-orange/10 text-orange border border-orange/20">
                                Resume Perfection: {run.resume_perfection_score}% · {run.resume_perfection_tier || "Evaluated"}
                              </span>
                            ) : (
                              <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-surface-muted text-bronze-dark/50">
                                Resume Quiz: Pending
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-bronze-dark/40 flex items-center gap-1.5">
                            <Clock className="w-3 h-3" />
                            Submitted: {run.submitted_at ? new Date(run.submitted_at).toLocaleString() : "Recently"}
                          </p>
                        </div>

                        <div className="flex gap-2">
                          <PBButton variant="secondary" size="sm" onClick={() => toggleReport(run.run_id)}>
                            {openPanel?.runId === run.run_id && openPanel?.kind === "report" ? "Hide Report" : "View Report"}
                          </PBButton>
                          <PBButton
                            variant="primary"
                            size="sm"
                            className="bg-success hover:bg-success/90 text-white"
                            onClick={() => handleDecide(run.run_id, "approved")}
                            disabled={actionLoading === run.run_id}
                          >
                            {actionLoading === run.run_id ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              "Approve"
                            )}
                          </PBButton>
                          <PBButton
                            variant="danger"
                            size="sm"
                            onClick={() => handleDecide(run.run_id, "rejected")}
                            disabled={actionLoading === run.run_id}
                          >
                            {actionLoading === run.run_id ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              "Reject"
                            )}
                          </PBButton>
                          <PBButton variant="secondary" size="sm"
                            onClick={() => setOpenPanel(openPanel?.runId === run.run_id && openPanel?.kind === "edit" ? null : { runId: run.run_id, kind: "edit" })}>
                            Edit
                          </PBButton>
                          {run.warnings?.length > 0 && (
                            <PBButton variant="outline" size="sm"
                              onClick={() => setOpenPanel(openPanel?.runId === run.run_id && openPanel?.kind === "override" ? null : { runId: run.run_id, kind: "override" })}>
                              Override
                            </PBButton>
                          )}
                        </div>
                        {openPanel?.runId === run.run_id && openPanel?.kind === "edit" && (
                          <div className="w-full space-y-2 pt-2">
                            <textarea value={note} onChange={e => setNote(e.target.value)} rows={2}
                              placeholder="Reviewer note shown to the student"
                              className="w-full px-3 py-2 text-sm bg-surface border border-border-default rounded-[10px]" />
                            {run.gaps?.length > 0 && (
                              <div className="flex gap-2">
                                <select value={gapSkill} onChange={e => setGapSkill(e.target.value)}
                                  className="px-3 py-2 text-sm bg-surface border border-border-default rounded-[10px]">
                                  <option value="">Rewrite a gap recommendation…</option>
                                  {run.gaps.map((g: string) => <option key={g} value={g}>{g}</option>)}
                                </select>
                                <input value={gapText} onChange={e => setGapText(e.target.value)} disabled={!gapSkill}
                                  placeholder="New recommendation (mention the skill)"
                                  className="flex-1 px-3 py-2 text-sm bg-surface border border-border-default rounded-[10px]" />
                              </div>
                            )}
                            <PBButton size="sm" onClick={() => handleEdit(run.run_id)}
                              disabled={actionLoading === run.run_id || (!note.trim() && !(gapSkill && gapText.trim()))}>
                              Save edit
                            </PBButton>
                          </div>
                        )}
                        {openPanel?.runId === run.run_id && openPanel?.kind === "report" && (
                          report ? <RunReport report={report} /> : <Loader2 className="w-4 h-4 animate-spin text-bronze" />
                        )}
                        {openPanel?.runId === run.run_id && openPanel?.kind === "override" && (
                          <div className="w-full space-y-2 pt-2">
                            <textarea value={reason} onChange={e => setReason(e.target.value)} rows={2}
                              placeholder="Reason for publishing despite the warnings (at least 20 characters)"
                              className="w-full px-3 py-2 text-sm bg-surface border border-border-default rounded-[10px]" />
                            <PBButton size="sm" onClick={() => handleOverride(run.run_id)}
                              disabled={actionLoading === run.run_id || reason.trim().length < 20}>
                              Override & publish
                            </PBButton>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Recent Decisions */}
              <div className="space-y-4">
                <h2 className="type-h3">Recent Decisions</h2>
                <div className="surface-card divide-y divide-border-subtle">
                  {queueData.recent_decisions.length === 0 ? (
                    <div className="p-8 text-center text-xs text-bronze-dark/40 italic">
                      No decisions recorded yet.
                    </div>
                  ) : (
                    queueData.recent_decisions.map((decision: any, idx: number) => (
                      <div key={idx} className="p-4 flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-charcoal">{decision.run_id.slice(0, 18)}...</p>
                          <p className="text-xs text-bronze-dark/40">
                            {decision.decided_at ? new Date(decision.decided_at).toLocaleTimeString() : "Recently"}
                          </p>
                        </div>
                        {decision.decision === "APPROVED" || decision.decision === "OVERRIDE" ? (
                          <span className="flex items-center gap-2 text-xs text-success font-semibold">
                            <CheckCircle className="w-3.5 h-3.5" /> {decision.decision === "OVERRIDE" ? "Overridden" : "Approved"}
                            {decision.rollback_to_version_id && (
                              <button onClick={() => handleRollback(decision.rollback_to_version_id)}
                                className="text-bronze-dark underline font-medium">
                                Roll back
                              </button>
                            )}
                          </span>
                        ) : decision.decision === "EDITED" ? (
                          <span className="text-xs text-bronze-dark font-semibold">Edited</span>
                        ) : (
                          <span className="flex items-center gap-1 text-xs text-danger font-semibold">
                            <XCircle className="w-3.5 h-3.5" /> Rejected
                          </span>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════════════════════════
            TAB 2: CAMPUS RECRUITMENT DRIVES
        ════════════════════════════════════════════════════════════ */}
        {activeTab === "drives" && (
          <div className="space-y-6 animate-fade-in">
            {/* Top Action Bar */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3 flex-1 max-w-xl">
                <div className="relative flex-1">
                  <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-bronze-dark/40" />
                  <input
                    type="text"
                    placeholder="Search drives by company, role, or skill..."
                    value={driveSearch}
                    onChange={(e) => setDriveSearch(e.target.value)}
                    className="w-full pl-9 pr-4 py-2 text-sm bg-surface border border-border-default rounded-xl focus:outline-none focus:border-orange"
                  />
                </div>
                <select
                  value={roleFamilyFilter}
                  onChange={(e) => setRoleFamilyFilter(e.target.value)}
                  className="px-3 py-2 text-sm bg-surface border border-border-default rounded-xl focus:outline-none focus:border-orange text-charcoal"
                >
                  <option value="all">All Domains</option>
                  <option value="software_engineering">Software Engineering</option>
                  <option value="data_engineering">Data Engineering</option>
                  <option value="devops">DevOps & Cloud</option>
                  <option value="analytics">Data Analytics</option>
                  <option value="core">Core Engineering</option>
                </select>
              </div>

              <PBButton
                variant="primary"
                onClick={() => setIsCreateModalOpen(true)}
                className="flex items-center gap-2 shrink-0 shadow-sm"
              >
                <Plus className="w-4 h-4" /> List New Company
              </PBButton>
            </div>

            {/* Drives Grid */}
            {drivesLoading ? (
              <div className="py-20 flex flex-col items-center justify-center gap-4 text-bronze-dark/50">
                <Loader2 className="w-8 h-8 animate-spin text-orange" />
                <p className="text-sm font-medium">Loading recruitment drives...</p>
              </div>
            ) : drives.length === 0 ? (
              <div className="surface-card p-12 text-center">
                <div className="w-14 h-14 rounded-2xl bg-surface-muted flex items-center justify-center mx-auto mb-4 text-bronze-dark/30">
                  <Building2 className="w-7 h-7" />
                </div>
                <h3 className="text-lg font-bold text-charcoal">No recruitment drives found</h3>
                <p className="text-sm text-bronze-dark/50 max-w-md mx-auto mt-1 mb-4">
                  {driveSearch || roleFamilyFilter !== "all"
                    ? "Try adjusting your filters or search terms."
                    : "No companies are currently listed for campus placement."}
                </p>
                <PBButton variant="primary" onClick={() => setIsCreateModalOpen(true)}>
                  <Plus className="w-4 h-4 mr-1.5" /> List First Company Drive
                </PBButton>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {drives.map((d) => (
                  <div
                    key={d.job_id}
                    className="surface-card p-5 rounded-2xl border border-border-default hover:border-orange/30 transition-all flex flex-col justify-between hover-lift"
                  >
                    <div className="space-y-3">
                      {/* Card Header */}
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-orange/10 text-orange flex items-center justify-center font-bold text-sm shrink-0">
                            {d.company_name.charAt(0)}
                          </div>
                          <div>
                            <h3 className="font-bold text-charcoal text-base font-zodiak leading-tight">
                              {d.company_name}
                            </h3>
                            <p className="text-xs text-bronze-dark/50">{d.industry || "Technology"}</p>
                          </div>
                        </div>
                        <span
                          className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
                            d.status === "active"
                              ? "bg-success-light text-success"
                              : "bg-surface-muted text-bronze-dark/70"
                          }`}
                        >
                          {d.status}
                        </span>
                      </div>

                      {/* Role title */}
                      <div>
                        <p className="font-semibold text-charcoal text-sm">{d.role_title}</p>
                        <p className="text-xs text-bronze-dark/50 capitalize">
                          {d.role_family.replace("_", " ")}
                        </p>
                      </div>

                      {/* Package & Cutoff */}
                      <div className="flex items-center gap-3 text-xs pt-1 border-t border-border-subtle flex-wrap">
                        <span className="font-bold text-orange flex items-center gap-1">
                          <DollarSign className="w-3.5 h-3.5" /> ₹{d.package_lpa} LPA
                        </span>
                        <span className="text-bronze-dark/70 flex items-center gap-1">
                          <GraduationCap className="w-3.5 h-3.5 text-bronze" /> Min CGPA: {d.min_cgpa}
                        </span>
                        {d.drive_date && (
                          <span className="text-bronze-dark/50 flex items-center gap-1">
                            <Calendar className="w-3.5 h-3.5 text-bronze" /> {d.drive_date}
                          </span>
                        )}
                      </div>

                      {/* Skills Tags */}
                      <div className="space-y-1.5 pt-1">
                        <p className="text-[11px] font-bold text-bronze-dark/50">REQUIRED SKILLS</p>
                        <div className="flex flex-wrap gap-1">
                          {d.required_skills.slice(0, 4).map((s) => (
                            <span
                              key={s}
                              className="text-[11px] px-2 py-0.5 bg-orange/8 text-orange border border-orange/15 rounded-md font-medium"
                            >
                              {s}
                            </span>
                          ))}
                          {d.required_skills.length > 4 && (
                            <span className="text-[11px] px-1.5 py-0.5 text-bronze-dark/40 font-medium">
                              +{d.required_skills.length - 4} more
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Card Actions */}
                    <div className="pt-4 mt-4 border-t border-border-subtle flex items-center justify-between gap-2">
                      <PBButton
                        variant="secondary"
                        size="sm"
                        className="text-xs flex items-center gap-1.5"
                        onClick={() => {
                          setSelectedCohortJob(d);
                          setIsCohortModalOpen(true);
                        }}
                      >
                        <BarChart3 className="w-3.5 h-3.5" /> Cohort Analytics
                      </PBButton>

                      <button
                        type="button"
                        onClick={() => handleDeleteDrive(d.job_id, d.company_name)}
                        className="p-2 text-bronze-dark/40 hover:text-danger hover:bg-danger-light rounded-lg transition-colors"
                        title="Delete drive"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {activeTab === "benchmarks" && <BenchmarkEditor />}
      </main>

      {/* Modals */}
      <CreateDriveModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onDriveCreated={handleDriveCreated}
      />

      <CohortAnalyticsModal
        job={selectedCohortJob}
        isOpen={isCohortModalOpen}
        onClose={() => setIsCohortModalOpen(false)}
      />
    </div>
  );
}
