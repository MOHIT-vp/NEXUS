"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  TrendingUp,
  BookOpen,
  Building2,
  Award,
  ArrowRight,
  ExternalLink,
  Sparkles,
  Calendar,
  DollarSign,
  GraduationCap,
  CheckCircle,
  Search,
  Filter,
  ShieldCheck,
} from "lucide-react";
import { Sidebar } from "@/components/navigation/sidebar";
import { MobileNav } from "@/components/navigation/mobile-nav";
import { ScoreGauge } from "@/components/ui/score-gauge";
import { PBBadge } from "@/components/ui/pb-badge";
import { PBButton } from "@/components/ui/pb-button";
import { Loader } from "@/components/ui/loader";
import { getDashboardByRunId, listRecruitmentDrives, JobDrive } from "@/lib/api";
import { PreparednessModal } from "@/components/companies/preparedness-modal";
import { CodingPractice } from "@/components/coding/coding-practice";
import { ResumePerfectionCard } from "@/components/resume/resume-perfection-card";

type CompanyMatch = {
  job_id?: string;
  company: string;
  role: string;
  match_score: number;
  confidence: string;
  package_lpa: number;
  matched_skills: string[];
  missing_skills: string[];
};

type RoadmapItem = {
  week: number;
  skill: string;
  action: string;
  resource: string;
  estimated_hours: number;
  priority: string;
};

type DashboardData = {
  student_name: string;
  github_username?: string;
  leetcode_handle?: string;
  placement_score: number;
  score_breakdown: { skills: number; coding: number; projects: number; cgpa: number };
  skill_gaps: { skill: string; severity: string; coverage: number }[];
  domain_coverage: Record<string, number>;
  company_matches: CompanyMatch[];
  top_companies: CompanyMatch[];
  roadmap: RoadmapItem[];
  profile: {
    skills: { name: string; proficiency: string }[];
    projects: { title: string; description: string; technologies: string[] }[];
    experiences: { company: string; role: string; duration: string }[];
    education?: { degree: string; institution: string; gpa?: number };
    summary: string;
  };
  stats: {
    total_skills: number;
    total_projects: number;
    total_experiences: number;
    coding_solved: number;
    gaps_open: number;
    strong_matches: number;
  };
  resume_perfection?: {
    status?: string;
    questions?: any[];
    evaluation?: any;
  };
};

const PRIORITY_MAP: Record<string, { variant: "critical" | "high" | "medium" | "low"; label: string }> = {
  critical: { variant: "critical", label: "Critical" },
  high: { variant: "high", label: "High" },
  medium: { variant: "medium", label: "Medium" },
  low: { variant: "low", label: "Low" },
};

function BreakdownBar({ label, pts, max }: { label: string; pts: number; max: number }) {
  const pct = (pts / max) * 100;
  return (
    <div>
      <div className="flex justify-between text-xs mb-1.5">
        <span className="font-medium text-charcoal">{label}</span>
        <span className="type-data text-sm">{pts.toFixed(0)}<span className="text-bronze-dark/40">/{max}</span></span>
      </div>
      <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bg-orange transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function DomainBar({ skill, pct }: { skill: string; pct: number }) {
  const color = pct >= 70 ? "#2D8A4E" : pct >= 40 ? "#C4820B" : "#C53030";
  return (
    <div>
      <div className="flex justify-between text-sm mb-1.5">
        <span className="font-medium text-charcoal capitalize">{skill}</span>
        <span className="text-xs font-bold" style={{ color }}>{pct}%</span>
      </div>
      <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

function MatchRow({
  m,
  rank,
  onCheck,
}: {
  m: CompanyMatch;
  rank: number;
  onCheck?: () => void;
}) {
  const color =
    m.match_score >= 75
      ? "text-success bg-success-light"
      : m.match_score >= 55
      ? "text-warning bg-warning-light"
      : "text-bronze-dark bg-surface-muted";
  return (
    <div className="flex items-center justify-between py-4 border-b border-border-subtle last:border-0 hover:bg-surface-warm/50 transition-colors px-1 -mx-1 rounded-lg">
      <div className="flex items-center gap-4 min-w-0">
        <span className="type-data text-bronze-dark/30 w-6 text-right shrink-0">{rank}</span>
        <div className="min-w-0">
          <p className="font-semibold text-charcoal text-[0.9375rem] truncate font-zodiak">{m.company}</p>
          <p className="text-xs text-bronze-dark/50">{m.role} · ₹{m.package_lpa} LPA</p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className={`text-xs font-bold px-2.5 py-1 rounded-full whitespace-nowrap ${color}`}>
          {m.match_score.toFixed(0)}%
        </span>
        {onCheck && (
          <button
            onClick={onCheck}
            className="text-xs text-orange font-semibold hover:underline hidden sm:block"
          >
            Check &rarr;
          </button>
        )}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();

  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  // Recruitment drives state
  const [drives, setDrives] = useState<JobDrive[]>([]);
  const [driveSearch, setDriveSearch] = useState("");
  const [driveRoleFamily, setDriveRoleFamily] = useState("all");
  const [selectedDrive, setSelectedDrive] = useState<JobDrive | null>(null);
  const [isPreparednessOpen, setIsPreparednessOpen] = useState(false);
  const [companySubTab, setCompanySubTab] = useState<"drives" | "matches">("drives");

  useEffect(() => {
    const runId = localStorage.getItem("active_run_id");
    setActiveRunId(runId);

    if (!runId) {
      router.replace("/onboarding");
      return;
    }

    const fetchData = async () => {
      try {
        const dashboardData = await getDashboardByRunId(runId);

        if (dashboardData.status === "published" || dashboardData.has_approved_plan) {
          setData(dashboardData.data as DashboardData);
          setLoading(false);
        } else {
          router.replace(`/assessment/${runId}`);
        }
      } catch (err) {
        console.error("Error fetching dashboard:", err);
        setLoading(false);
      }
    };

    const fetchDrives = async () => {
      try {
        const driveList = await listRecruitmentDrives();
        setDrives(driveList);
      } catch (err) {
        console.error("Failed to load drives:", err);
      }
    };

    fetchData();
    fetchDrives();
  }, [router]);

  const handleOpenPreparedness = (drive: JobDrive) => {
    setSelectedDrive(drive);
    setIsPreparednessOpen(true);
  };

  const handleOpenPreparednessFromMatch = (match: CompanyMatch) => {
    // Find matching drive by job_id or company name
    const found =
      (match.job_id ? drives.find(d => d.job_id === match.job_id) : null) ||
      drives.find(d => d.company_name.toLowerCase() === match.company.toLowerCase()) ||
      drives.find(d => match.company.toLowerCase().includes(d.company_name.toLowerCase()) || d.company_name.toLowerCase().includes(match.company.toLowerCase()));

    if (found) {
      setSelectedDrive(found);
    } else {
      const proxyDrive: JobDrive = {
        job_id: match.job_id || `job-${match.company.toLowerCase().replace(/\s+/g, "-")}`,
        company_id: `comp-proxy`,
        company_name: match.company,
        role_title: match.role,
        role_family: "software_engineering",
        package_lpa: match.package_lpa,
        min_cgpa: 7.0,
        max_backlogs: 0,
        min_experience: 0,
        required_skills: match.matched_skills.concat(match.missing_skills),
        preferred_skills: [],
        status: "upcoming",
        selection_rounds: [
          { round_number: 1, name: "Online Coding Assessment", type: "coding_test", duration_minutes: 90 },
          { round_number: 2, name: "Technical Interview", type: "technical_interview", duration_minutes: 60 },
          { round_number: 3, name: "HR Interview", type: "hr", duration_minutes: 30 },
        ],
      };
      setSelectedDrive(proxyDrive);
    }
    setIsPreparednessOpen(true);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-ivory">
        <div className="flex flex-col items-center gap-12 mt-10">
          <Loader />
          <p className="text-sm text-bronze-dark/50 font-medium">Loading your placement dashboard...</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-ivory gap-6 p-8 text-center">
        <div className="w-16 h-16 rounded-[16px] bg-warning-light flex items-center justify-center">
          <AlertTriangle className="w-7 h-7 text-warning" />
        </div>
        <h1 className="type-h2 text-charcoal">Unable to load dashboard</h1>
        <p className="type-body text-bronze-dark/50 max-w-sm">
          We couldn't load your assessment data. Please start a new assessment.
        </p>
        <PBButton onClick={() => router.push("/onboarding")} size="lg">
          Start your assessment <ArrowRight className="w-4 h-4 ml-2" />
        </PBButton>
      </div>
    );
  }

  const { stats, placement_score, score_breakdown, skill_gaps, domain_coverage,
    top_companies, company_matches, roadmap, profile } = data;

  const studentGpa = profile.education?.gpa || score_breakdown.cgpa;

  // Filter drives
  const filteredDrives = drives.filter(d => {
    if (driveRoleFamily !== "all" && d.role_family.toLowerCase() !== driveRoleFamily.toLowerCase()) {
      return false;
    }
    if (driveSearch) {
      const term = driveSearch.toLowerCase();
      const matchesName = d.company_name.toLowerCase().includes(term);
      const matchesRole = d.role_title.toLowerCase().includes(term);
      const matchesSkill = d.required_skills.some(s => s.toLowerCase().includes(term));
      if (!matchesName && !matchesRole && !matchesSkill) return false;
    }
    return true;
  });

  return (
    <div className="min-h-screen bg-ivory flex">
      {/* Sidebar */}
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} studentName={data.student_name} />

      {/* Main content */}
      <div className="flex-1 min-w-0">
        {/* Top bar */}
        <header className="sticky top-0 z-10 bg-ivory/90 backdrop-blur-sm border-b border-border-subtle px-6 lg:px-8 py-4 flex items-center justify-between">
          <div>
            <p className="type-body text-bronze-dark/50">
              Career readiness & placement intelligence
            </p>
            <h1 className="text-lg font-semibold text-charcoal">
              {data.student_name ? `Welcome, ${data.student_name}` : "Your Placement Portal"}
            </h1>
          </div>
          <div className="hidden sm:flex items-center gap-4">
            <span className="text-xs bg-orange/10 text-orange font-semibold px-3 py-1 rounded-full">
              {drives.length} Visiting Companies
            </span>
          </div>
        </header>

        <main className="px-6 lg:px-8 py-8 space-y-8 pb-24 lg:pb-8">
          {/* ── Metric Cards ── */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              {
                label: "Placement Score",
                value: `${Math.round(placement_score)}/100`,
                sub: `Skills ${score_breakdown.skills}pts · Coding ${score_breakdown.coding.toFixed(0)}pts`,
              },
              {
                label: "Campus Drives",
                value: String(drives.length),
                sub: "Active recruitment visiting",
                tab: "companies",
              },
              {
                label: "Skill Gaps Open",
                value: String(stats.gaps_open),
                sub: `${skill_gaps.filter(g => g.severity === "high").length} high priority`,
                tab: "roadmap",
              },
              {
                label: "Problems Solved",
                value: String(stats?.coding_solved ?? 0),
                sub: "Practice challenges →",
                tab: "coding",
              },
            ].map(card => (
              <div
                key={card.label}
                onClick={() => card.tab && setActiveTab(card.tab)}
                className={`surface-card p-5 ${
                  card.tab ? "cursor-pointer hover:border-orange/40 hover-lift transition-all" : ""
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <p className="type-micro">{card.label}</p>
                  {card.tab && (
                    <span className="text-[10px] text-orange font-semibold hidden sm:inline">
                      View
                    </span>
                  )}
                </div>
                <p className="text-2xl font-bold text-charcoal mb-1">{card.value}</p>
                <p className="text-xs text-bronze-dark/40">{card.sub}</p>
              </div>
            ))}
          </div>

          {/* ── Mobile Tab Selector ── */}
          <div className="flex gap-1 p-1 bg-surface-muted rounded-[12px] lg:hidden overflow-x-auto">
            {["overview", "perfection", "companies", "roadmap", "skills", "coding"].map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-1 min-w-max text-sm font-semibold py-2 px-3 rounded-[10px] transition-colors capitalize whitespace-nowrap ${
                  activeTab === tab ? "bg-surface text-charcoal shadow-xs" : "text-bronze-dark/50"
                }`}
              >
                {tab === "perfection" ? "Resume Perfection" : tab === "companies" ? "Recruitment & Companies" : tab === "coding" ? "Code Practice" : tab}
              </button>
            ))}
          </div>

          {/* ═══════════════════════════════════════════
              OVERVIEW TAB
          ═══════════════════════════════════════════ */}
          {activeTab === "overview" && (
            <div className="space-y-6 animate-fade-in">
              {/* Upcoming Recruitment Drives Alert Banner */}
              {drives.length > 0 && (
                <div className="surface-warm p-5 rounded-2xl border border-orange/20 flex flex-col sm:flex-row items-center justify-between gap-4">
                  <div className="flex items-center gap-3.5">
                    <div className="w-10 h-10 rounded-xl bg-orange/15 text-orange flex items-center justify-center shrink-0">
                      <Building2 className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-bold text-charcoal text-sm font-zodiak">
                        {drives.length} Campus Recruitment Drives Listed
                      </h3>
                      <p className="text-xs text-bronze-dark/60 mt-0.5">
                        New companies have posted job openings. Check your skill match and readiness before drive dates.
                      </p>
                    </div>
                  </div>
                  <PBButton
                    variant="primary"
                    size="sm"
                    className="shrink-0 text-xs"
                    onClick={() => setActiveTab("companies")}
                  >
                    View Drives & Check Preparedness <ArrowRight className="w-3.5 h-3.5 ml-1" />
                  </PBButton>
                </div>
              )}

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Score + breakdown */}
                <div className="lg:col-span-4 surface-card p-6 flex flex-col items-center gap-5">
                  <h2 className="type-micro self-start">READINESS SCORE</h2>
                  <ScoreGauge score={placement_score} />
                  <div className="w-full space-y-3 mt-2">
                    <BreakdownBar label="Skill Coverage" pts={score_breakdown.skills} max={40} />
                    <BreakdownBar label="Coding Activity" pts={score_breakdown.coding} max={30} />
                    <BreakdownBar label="Projects & Experience" pts={score_breakdown.projects} max={20} />
                    <BreakdownBar label="CGPA" pts={score_breakdown.cgpa} max={10} />
                  </div>
                </div>

                {/* Skill coverage */}
                <div className="lg:col-span-4 surface-card p-6">
                  <h2 className="type-micro mb-5">DOMAIN COVERAGE</h2>
                  <div className="space-y-4">
                    {Object.entries(domain_coverage).map(([skill, pct]) => (
                      <DomainBar key={skill} skill={skill} pct={pct} />
                    ))}
                    {Object.keys(domain_coverage).length === 0 && (
                      <p className="text-sm text-bronze-dark/40 italic">No domain coverage data — add more skills to your resume.</p>
                    )}
                  </div>
                </div>

                {/* Top matches */}
                <div className="lg:col-span-4 surface-card p-6">
                  <h2 className="type-micro mb-5 flex items-center gap-2">
                    <Building2 className="w-3.5 h-3.5 text-bronze" /> TOP COMPANY MATCHES
                  </h2>
                  <div>
                    {top_companies.map((m, i) => (
                      <MatchRow
                        key={i}
                        m={m}
                        rank={i + 1}
                        onCheck={() => handleOpenPreparednessFromMatch(m)}
                      />
                    ))}
                  </div>
                  <button
                    onClick={() => setActiveTab("companies")}
                    className="mt-4 text-sm font-medium text-orange hover:text-orange-deep transition-colors flex items-center gap-1"
                  >
                    View all campus drives <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* AI Summary */}
                {profile.summary && (
                  <div className="lg:col-span-12 surface-warm p-6 rounded-[16px]">
                    <h2 className="type-micro mb-3 flex items-center gap-2">
                      <Award className="w-3.5 h-3.5 text-bronze" /> AI PROFILE SUMMARY
                    </h2>
                    <p className="type-body leading-relaxed">{profile.summary}</p>
                  </div>
                )}

                {/* Resume Perfection & Authenticity Card */}
                <div className="lg:col-span-12 surface-card p-6 border-l-4 border-l-orange rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-6">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-orange/10 text-orange flex items-center justify-center shrink-0">
                      <ShieldCheck className="w-6 h-6" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <h3 className="font-bold text-charcoal text-base">Resume Perfection & Authenticity</h3>
                        {data.resume_perfection?.evaluation ? (
                          <span
                            className="text-[11px] font-bold px-2.5 py-0.5 rounded-full text-white uppercase tracking-wider"
                            style={{ backgroundColor: data.resume_perfection.evaluation.tier_color || "#2D8A4E" }}
                          >
                            {data.resume_perfection.evaluation.tier_label} ({data.resume_perfection.evaluation.overall_score}%)
                          </span>
                        ) : (
                          <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-warning-light text-warning uppercase tracking-wider">
                            Verification Pending
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-bronze-dark/70 max-w-2xl leading-relaxed">
                        {data.resume_perfection?.evaluation
                          ? data.resume_perfection.evaluation.summary
                          : "Evaluate your technical mastery and claim authenticity with 5 targeted questions probing the projects and skills on your resume before interviewers cross-examine you."}
                      </p>
                    </div>
                  </div>

                  <PBButton
                    variant="primary"
                    size="sm"
                    className="shrink-0"
                    onClick={() => setActiveTab("perfection")}
                  >
                    {data.resume_perfection?.evaluation ? (
                      <>
                        View Full Scorecard & Defense Tips <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                      </>
                    ) : (
                      <>
                        Take Resume Perfection Quiz <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                      </>
                    )}
                  </PBButton>
                </div>
              </div>
            </div>
          )}

          {/* ═══════════════════════════════════════════
              RESUME PERFECTION TAB
          ═══════════════════════════════════════════ */}
          {activeTab === "perfection" && activeRunId && (
            <div className="space-y-6 animate-fade-in">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h2 className="type-h2 mb-1">Resume Perfection & Claim Verification</h2>
                  <p className="type-body text-bronze-dark/50">
                    Evaluate your technical depth, verify project claims, and prepare bulletproof defenses for campus placement rounds.
                  </p>
                </div>
              </div>
              <ResumePerfectionCard
                runId={activeRunId}
                initialEvaluation={data.resume_perfection?.evaluation}
                initialQuestions={data.resume_perfection?.questions}
                onEvaluationComplete={(evalResult) => {
                  setData((prev) =>
                    prev
                      ? {
                          ...prev,
                          resume_perfection: {
                            ...(prev.resume_perfection || {}),
                            status: "evaluated",
                            evaluation: evalResult,
                          },
                        }
                      : prev
                  );
                }}
              />
            </div>
          )}

          {/* ═══════════════════════════════════════════
              COMPANY MATCHES & DRIVES TAB
          ═══════════════════════════════════════════ */}
          {activeTab === "companies" && (
            <div className="space-y-6 animate-fade-in">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h2 className="type-h2 mb-1">Campus Recruitment Drives</h2>
                  <p className="type-body text-bronze-dark/50">
                    Companies visiting for recruitment. Check your preparedness and skill match with their requirements.
                  </p>
                </div>

                {/* Sub Tab Switcher */}
                <div className="flex p-1 bg-surface-muted rounded-xl self-start sm:self-auto text-xs font-semibold">
                  <button
                    onClick={() => setCompanySubTab("drives")}
                    className={`px-3 py-1.5 rounded-lg transition-all ${
                      companySubTab === "drives"
                        ? "bg-surface text-charcoal shadow-xs"
                        : "text-bronze-dark/60 hover:text-charcoal"
                    }`}
                  >
                    Visiting Drives ({drives.length})
                  </button>
                  <button
                    onClick={() => setCompanySubTab("matches")}
                    className={`px-3 py-1.5 rounded-lg transition-all ${
                      companySubTab === "matches"
                        ? "bg-surface text-charcoal shadow-xs"
                        : "text-bronze-dark/60 hover:text-charcoal"
                    }`}
                  >
                    All Market Matches ({company_matches.length})
                  </button>
                </div>
              </div>

              {/* ── Sub Tab: Visiting Drives ── */}
              {companySubTab === "drives" && (
                <div className="space-y-6">
                  {/* Filter & Search Bar */}
                  <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                    <div className="relative flex-1">
                      <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-bronze-dark/40" />
                      <input
                        type="text"
                        placeholder="Search drives by company name, role, or skills..."
                        value={driveSearch}
                        onChange={(e) => setDriveSearch(e.target.value)}
                        className="w-full pl-9 pr-4 py-2 text-sm bg-surface border border-border-default rounded-xl focus:outline-none focus:border-orange"
                      />
                    </div>
                    <select
                      value={driveRoleFamily}
                      onChange={(e) => setDriveRoleFamily(e.target.value)}
                      className="px-3 py-2 text-sm bg-surface border border-border-default rounded-xl focus:outline-none focus:border-orange text-charcoal"
                    >
                      <option value="all">All Domains</option>
                      <option value="software_engineering">Software Engineering</option>
                      <option value="data_engineering">Data Engineering</option>
                      <option value="devops">DevOps & Cloud</option>
                      <option value="analytics">Analytics</option>
                      <option value="core">Core Engineering</option>
                    </select>
                  </div>

                  {/* Drives Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                    {filteredDrives.map((d) => {
                      const isEligible = !studentGpa || studentGpa >= d.min_cgpa;
                      return (
                        <div
                          key={d.job_id}
                          className="surface-card p-5 rounded-2xl border border-border-default hover:border-orange/40 transition-all flex flex-col justify-between hover-lift"
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
                              <PBBadge variant="medium">{d.role_family.replace("_", " ")}</PBBadge>
                            </div>

                            {/* Role title */}
                            <div>
                              <p className="font-semibold text-charcoal text-sm">{d.role_title}</p>
                              <div className="flex items-center gap-3 text-xs text-bronze-dark/60 mt-1">
                                <span className="font-bold text-orange flex items-center gap-0.5">
                                  <DollarSign className="w-3.5 h-3.5" /> ₹{d.package_lpa} LPA
                                </span>
                                {d.drive_date && (
                                  <span className="flex items-center gap-1">
                                    <Calendar className="w-3.5 h-3.5 text-bronze" /> {d.drive_date}
                                  </span>
                                )}
                              </div>
                            </div>

                            {/* Cutoff & Eligibility Pill */}
                            <div className="pt-2 border-t border-border-subtle flex items-center justify-between text-xs">
                              <span className="text-bronze-dark/60 flex items-center gap-1">
                                <GraduationCap className="w-3.5 h-3.5" /> Cutoff: {d.min_cgpa} CGPA
                              </span>
                              {isEligible ? (
                                <span className="text-[11px] font-semibold text-success bg-success-light px-2 py-0.5 rounded-full flex items-center gap-1">
                                  <CheckCircle className="w-3 h-3" /> Eligible
                                </span>
                              ) : (
                                <span className="text-[11px] font-semibold text-danger bg-danger-light px-2 py-0.5 rounded-full flex items-center gap-1">
                                  <AlertTriangle className="w-3 h-3" /> CGPA Shortfall
                                </span>
                              )}
                            </div>

                            {/* Required Skills Chips */}
                            <div className="space-y-1.5 pt-1">
                              <p className="text-[10px] font-bold text-bronze-dark/50 uppercase tracking-wide">
                                Key Requirements
                              </p>
                              <div className="flex flex-wrap gap-1">
                                {d.required_skills.slice(0, 4).map((s) => (
                                  <span
                                    key={s}
                                    className="text-[11px] px-2 py-0.5 bg-surface-muted text-charcoal border border-border-subtle rounded-md font-medium"
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

                          {/* Action Button */}
                          <div className="pt-4 mt-4 border-t border-border-subtle">
                            <PBButton
                              variant="primary"
                              size="sm"
                              className="w-full flex items-center justify-center gap-1.5 shadow-sm"
                              onClick={() => handleOpenPreparedness(d)}
                            >
                              <Sparkles className="w-3.5 h-3.5" /> Check Preparedness & Skill Match
                            </PBButton>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {filteredDrives.length === 0 && (
                    <div className="surface-card p-12 text-center">
                      <p className="text-charcoal font-semibold mb-1">No matching recruitment drives found.</p>
                      <p className="text-xs text-bronze-dark/50">Try clearing your search or domain filter.</p>
                    </div>
                  )}
                </div>
              )}

              {/* ── Sub Tab: All Market Matches Table ── */}
              {companySubTab === "matches" && (
                <div className="surface-card overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border-default bg-surface-warm">
                          {["Company", "Role", "Match", "Package", "Confidence", "Missing Skills", "Action"].map(h => (
                            <th key={h} className="text-left px-5 py-3 type-micro whitespace-nowrap">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {company_matches.map((m, i) => {
                          const matchColor =
                            m.match_score >= 75
                              ? "text-success bg-success-light"
                              : m.match_score >= 55
                              ? "text-warning bg-warning-light"
                              : "text-bronze-dark bg-surface-muted";
                          return (
                            <tr key={i} className="border-b border-border-subtle hover:bg-surface-warm/50 transition-colors">
                              <td className="px-5 py-4 font-semibold text-charcoal font-zodiak">{m.company}</td>
                              <td className="px-5 py-4 text-bronze-dark/70">{m.role}</td>
                              <td className="px-5 py-4">
                                <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${matchColor}`}>
                                  {m.match_score.toFixed(0)}%
                                </span>
                              </td>
                              <td className="px-5 py-4 text-charcoal">₹{m.package_lpa} LPA</td>
                              <td className="px-5 py-4">
                                <PBBadge variant={m.confidence === "High" ? "success" : m.confidence === "Moderate" ? "medium" : "low"}>
                                  {m.confidence}
                                </PBBadge>
                              </td>
                              <td className="px-5 py-4 text-xs text-bronze-dark/50 max-w-xs">
                                {m.missing_skills.length > 0 ? (
                                  m.missing_skills.join(", ")
                                ) : (
                                  <span className="text-success font-semibold">None ✓</span>
                                )}
                              </td>
                              <td className="px-5 py-4">
                                <PBButton
                                  variant="secondary"
                                  size="sm"
                                  className="text-xs"
                                  onClick={() => handleOpenPreparednessFromMatch(m)}
                                >
                                  Check &rarr;
                                </PBButton>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ═══════════════════════════════════════════
              ROADMAP TAB
          ═══════════════════════════════════════════ */}
          {activeTab === "roadmap" && (
            <div className="animate-fade-in">
              <div className="mb-6">
                <h2 className="type-h2 mb-1">Your learning roadmap.</h2>
                <p className="type-body text-bronze-dark/50">A structured plan to close your skill gaps and strengthen your placement readiness.</p>
              </div>

              {roadmap.length === 0 ? (
                <div className="surface-card p-12 text-center">
                  <div className="w-12 h-12 rounded-[14px] bg-success-light flex items-center justify-center mx-auto mb-4">
                    <TrendingUp className="w-5 h-5 text-success" />
                  </div>
                  <h3 className="font-bold text-lg text-charcoal">Excellent coverage!</h3>
                  <p className="text-sm text-bronze-dark/50 mt-1">No critical skill gaps were identified from your resume.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {roadmap.map((item, i) => {
                    const priority = PRIORITY_MAP[item.priority] || PRIORITY_MAP.low;
                    return (
                      <div key={i} className="surface-card p-5 flex items-start gap-5 hover-lift">
                        <div className="w-10 h-10 rounded-full bg-earth flex items-center justify-center text-ivory text-sm font-bold shrink-0">
                          W{item.week}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap mb-1">
                            <h3 className="font-semibold text-charcoal">{item.action}</h3>
                            <PBBadge variant={priority.variant}>{priority.label}</PBBadge>
                          </div>
                          <p className="text-sm text-bronze flex items-center gap-1.5">
                            <BookOpen className="w-3.5 h-3.5 shrink-0" />
                            {item.resource}
                          </p>
                          <p className="text-xs text-bronze-dark/40 mt-1">~{item.estimated_hours} hours estimated</p>
                        </div>
                        <div className="text-right text-xs text-bronze-dark/40 shrink-0 hidden sm:block">
                          <TrendingUp className="w-3.5 h-3.5 inline mb-0.5" /> <span className="font-semibold capitalize">{item.skill}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* ═══════════════════════════════════════════
              SKILLS TAB
          ═══════════════════════════════════════════ */}
          {activeTab === "skills" && (
            <div className="space-y-6 animate-fade-in">
              <div className="surface-card p-6">
                <h2 className="font-semibold text-charcoal mb-4">Extracted Skills ({profile.skills.length})</h2>
                <div className="flex flex-wrap gap-2">
                  {profile.skills.map((s, i) => {
                    const variant =
                      s.proficiency === "advanced" || s.proficiency === "expert" ? "success" :
                      s.proficiency === "intermediate" ? "medium" : "low";
                    return (
                      <PBBadge key={i} variant={variant}>
                        {s.name} · {s.proficiency}
                      </PBBadge>
                    );
                  })}
                </div>
              </div>

              {profile.projects.length > 0 && (
                <div className="surface-card p-6">
                  <h2 className="font-semibold text-charcoal mb-4">Projects ({profile.projects.length})</h2>
                  <div className="space-y-4">
                    {profile.projects.map((p, i) => (
                      <div key={i} className="p-4 surface-warm rounded-[12px]">
                        <h3 className="font-semibold text-charcoal">{p.title}</h3>
                        <p className="text-sm text-bronze-dark/60 mt-1 leading-relaxed">{p.description}</p>
                        <div className="flex flex-wrap gap-1.5 mt-3">
                          {p.technologies?.map((t, j) => (
                            <span key={j} className="text-xs bg-surface border border-border-subtle text-bronze-dark px-2 py-0.5 rounded-full">{t}</span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {profile.experiences.length > 0 && (
                <div className="surface-card p-6">
                  <h2 className="font-semibold text-charcoal mb-4">Experience ({profile.experiences.length})</h2>
                  <div className="space-y-3">
                    {profile.experiences.map((e, i) => (
                      <div key={i} className="flex items-center justify-between p-4 surface-warm rounded-[12px]">
                        <div>
                          <p className="font-semibold text-charcoal">{e.role}</p>
                          <p className="text-sm text-bronze-dark/50 font-zodiak">{e.company}</p>
                        </div>
                        <span className="text-xs text-bronze-dark/40 shrink-0">{e.duration}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ═══════════════════════════════════════════
              CODING PRACTICE TAB
          ═══════════════════════════════════════════ */}
          {activeTab === "coding" && (
            <CodingPractice />
          )}
        </main>
      </div>

      {/* Preparedness & Skill Match Modal */}
      <PreparednessModal
        job={selectedDrive}
        isOpen={isPreparednessOpen}
        onClose={() => setIsPreparednessOpen(false)}
        studentRunId={activeRunId}
      />

      {/* Mobile nav */}
      <MobileNav activeTab={activeTab} onTabChange={setActiveTab} />
    </div>
  );
}
