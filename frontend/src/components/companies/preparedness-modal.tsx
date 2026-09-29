"use client";

import { useEffect, useState } from "react";
import {
  X,
  CheckCircle,
  AlertTriangle,
  Building2,
  Calendar,
  DollarSign,
  GraduationCap,
  BookOpen,
  Sparkles,
  Zap,
  Loader2,
} from "lucide-react";
import { PBBadge } from "@/components/ui/pb-badge";
import { PBButton } from "@/components/ui/pb-button";
import { ScoreGauge } from "@/components/ui/score-gauge";
import { checkCompanyPreparedness, JobDrive, PreparednessCheckResult } from "@/lib/api";

interface PreparednessModalProps {
  job: JobDrive | null;
  isOpen: boolean;
  onClose: () => void;
  studentRunId?: string | null;
}

export function PreparednessModal({ job, isOpen, onClose, studentRunId }: PreparednessModalProps) {
  const [data, setData] = useState<PreparednessCheckResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"report" | "roadmap" | "simulator">("report");

  // What-If Simulator state
  const [simulatedSkills, setSimulatedSkills] = useState<string[]>([]);
  const [additionalProblems, setAdditionalProblems] = useState<number>(20);
  const [simulating, setSimulating] = useState(false);
  const [simulatedResult, setSimulatedResult] = useState<PreparednessCheckResult | null>(null);

  useEffect(() => {
    if (!isOpen || !job) return;

    const fetchAssessment = async () => {
      setLoading(true);
      setError(null);
      setSimulatedResult(null);
      setSimulatedSkills([]);

      try {
        const res = await checkCompanyPreparedness(job.job_id, {
          run_id: studentRunId || undefined,
        });
        setData(res);
      } catch (err: unknown) {
        console.error("Failed to check preparedness:", err);
        const msg = err instanceof Error ? err.message : "Unable to compute preparedness evaluation. Please try again.";
        setError(msg);
      } finally {
        setLoading(false);
      }
    };

    fetchAssessment();
  }, [isOpen, job, studentRunId]);

  if (!isOpen || !job) return null;

  // Run What-If Simulation
  const handleRunSimulation = async () => {
    if (!data) return;
    setSimulating(true);

    try {
      // Merge current matched skills + newly checked simulated skills
      const currentSkills = data.matched_skills.map(s => s.name);
      const combinedSkills = Array.from(new Set([...currentSkills, ...simulatedSkills]));
      const baseProblems = data.student_coding_solved || 120;

      const res = await checkCompanyPreparedness(job.job_id, {
        skills: combinedSkills,
        cgpa: data.student_cgpa || undefined,
        backlogs: data.student_backlogs ?? undefined,
        coding_solved: baseProblems + additionalProblems,
      });
      setSimulatedResult(res);
    } catch (err) {
      console.error("Simulation failed:", err);
    } finally {
      setSimulating(false);
    }
  };

  const toggleSimulatedSkill = (skill: string) => {
    if (simulatedSkills.includes(skill)) {
      setSimulatedSkills(simulatedSkills.filter(s => s !== skill));
    } else {
      setSimulatedSkills([...simulatedSkills, skill]);
    }
  };

  const displayData = simulatedResult || data;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-charcoal/50 backdrop-blur-sm animate-fade-in overflow-y-auto">
      <div className="surface-card bg-ivory w-full max-w-3xl rounded-2xl shadow-2xl border border-border-default my-6 flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="p-6 border-b border-border-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="w-12 h-12 rounded-xl bg-orange/10 flex items-center justify-center text-orange shrink-0 mt-0.5">
              <Building2 className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-xl font-bold text-charcoal font-zodiak">{job.company_name}</h2>
                <PBBadge variant="medium">{job.role_family.replace("_", " ")}</PBBadge>
                {job.status === "active" ? (
                  <span className="text-xs bg-success-light text-success font-semibold px-2 py-0.5 rounded-full">
                    Recruitment Open
                  </span>
                ) : (
                  <span className="text-xs bg-surface-muted text-bronze-dark/60 font-semibold px-2 py-0.5 rounded-full">
                    Upcoming Drive
                  </span>
                )}
              </div>
              <p className="text-sm font-semibold text-charcoal/90 mt-0.5">{job.role_title}</p>
              <div className="flex items-center gap-4 text-xs text-bronze-dark/60 mt-1 flex-wrap">
                <span className="flex items-center gap-1 font-semibold text-charcoal">
                  <DollarSign className="w-3.5 h-3.5 text-orange" /> ₹{job.package_lpa} LPA
                </span>
                <span className="flex items-center gap-1">
                  <GraduationCap className="w-3.5 h-3.5 text-bronze" /> Min CGPA: {job.min_cgpa}
                </span>
                {job.drive_date && (
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5 text-bronze" /> Drive Date: {job.drive_date}
                  </span>
                )}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-surface-muted text-bronze-dark/50 hover:text-charcoal transition-colors self-start sm:self-center"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="px-6 pt-3 border-b border-border-subtle flex gap-4 text-sm font-medium">
          <button
            onClick={() => setActiveTab("report")}
            className={`pb-3 border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "report"
                ? "border-orange text-orange font-semibold"
                : "border-transparent text-bronze-dark/60 hover:text-charcoal"
            }`}
          >
            <Sparkles className="w-4 h-4" /> Preparedness Report
          </button>
          <button
            onClick={() => setActiveTab("roadmap")}
            className={`pb-3 border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "roadmap"
                ? "border-orange text-orange font-semibold"
                : "border-transparent text-bronze-dark/60 hover:text-charcoal"
            }`}
          >
            <BookOpen className="w-4 h-4" /> 2-Week Prep Roadmap
          </button>
          <button
            onClick={() => setActiveTab("simulator")}
            className={`pb-3 border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "simulator"
                ? "border-orange text-orange font-semibold"
                : "border-transparent text-bronze-dark/60 hover:text-charcoal"
            }`}
          >
            <Zap className="w-4 h-4" /> What-If Simulator
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {loading ? (
            <div className="py-16 flex flex-col items-center justify-center gap-4 text-bronze-dark/50">
              <Loader2 className="w-8 h-8 animate-spin text-orange" />
              <p className="text-sm font-medium">Running deterministic skill match against {job.company_name} requirements...</p>
            </div>
          ) : error ? (
            <div className="p-4 bg-danger-light text-danger rounded-xl border border-danger/20 text-sm">
              {error}
            </div>
          ) : displayData ? (
            <>
              {/* ══════════════════════════════════════════════════
                  TAB 1: PREPAREDNESS REPORT
              ══════════════════════════════════════════════════ */}
              {activeTab === "report" && (
                <div className="space-y-6 animate-fade-in">
                  {/* Readiness Banner */}
                  <div className="surface-warm p-5 rounded-2xl border border-border-default flex flex-col sm:flex-row items-center justify-between gap-6">
                    <div className="flex items-center gap-5">
                      <ScoreGauge score={displayData.overall_score} size={110} />
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${
                              displayData.match_tier === "Highly Prepared"
                                ? "bg-success-light text-success"
                                : displayData.match_tier === "Competitive Fit"
                                ? "bg-warning-light text-warning"
                                : "bg-danger-light text-danger"
                            }`}
                          >
                            {displayData.match_tier}
                          </span>
                          <span className="text-xs text-bronze-dark/50">
                            Confidence: {Math.round(displayData.confidence * 100)}%
                          </span>
                        </div>
                        <h3 className="text-xl font-bold text-charcoal font-zodiak">
                          {displayData.match_percentage}% Preparedness Match
                        </h3>
                        <p className="text-xs text-bronze-dark/60 mt-0.5">
                          {displayData.match_tier === "Highly Prepared"
                            ? "Excellent profile alignment. You are well-positioned to clear the initial rounds."
                            : displayData.match_tier === "Competitive Fit"
                            ? "Solid foundation. Address 1 or 2 core skill gaps before the drive."
                            : "Substantial gaps detected. Follow the tailored 2-week roadmap below."}
                        </p>
                      </div>
                    </div>

                    {/* Eligibility Status Pill */}
                    <div className="shrink-0 w-full sm:w-auto">
                      {displayData.is_eligible ? (
                        <div className="p-3 bg-success-light/80 border border-success/30 rounded-xl text-left">
                          <div className="flex items-center gap-1.5 text-success font-semibold text-xs mb-0.5">
                            <CheckCircle className="w-4 h-4" /> Eligible for Drive
                          </div>
                          <p className="text-[11px] text-bronze-dark/60">
                            CGPA &ge; {job.min_cgpa} {job.max_backlogs !== undefined ? `· Max backlogs: ${job.max_backlogs}` : ""}
                          </p>
                        </div>
                      ) : (
                        <div className="p-3 bg-danger-light border border-danger/30 rounded-xl text-left">
                          <div className="flex items-center gap-1.5 text-danger font-semibold text-xs mb-0.5">
                            <AlertTriangle className="w-4 h-4" /> Criteria Shortfall
                          </div>
                          <p className="text-[11px] text-bronze-dark/60 max-w-xs">
                            {displayData.eligibility_reasons[0] || `Cutoff: CGPA ${job.min_cgpa}`}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Score Breakdown Bars */}
                  <div className="surface-card p-5 space-y-3">
                    <h3 className="type-micro text-bronze-dark/70">DETERMINISTIC EVALUATION BREAKDOWN</h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                      <div>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="font-semibold text-charcoal">Skill Coverage</span>
                          <span className="type-data text-xs font-bold text-orange">
                            {displayData.breakdown.skill_coverage.score.toFixed(1)} / {displayData.breakdown.skill_coverage.max} pts
                          </span>
                        </div>
                        <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-orange rounded-full"
                            style={{ width: `${displayData.breakdown.skill_coverage.percentage}%` }}
                          />
                        </div>
                      </div>

                      <div>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="font-semibold text-charcoal">Coding Activity & DSA</span>
                          <span className="type-data text-xs font-bold text-orange">
                            {displayData.breakdown.coding_performance.score.toFixed(1)} / {displayData.breakdown.coding_performance.max} pts
                          </span>
                        </div>
                        <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-orange rounded-full"
                            style={{ width: `${displayData.breakdown.coding_performance.percentage}%` }}
                          />
                        </div>
                      </div>

                      <div>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="font-semibold text-charcoal">Project Relevance</span>
                          <span className="type-data text-xs font-bold text-orange">
                            {displayData.breakdown.project_relevance.score.toFixed(1)} / {displayData.breakdown.project_relevance.max} pts
                          </span>
                        </div>
                        <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-orange rounded-full"
                            style={{ width: `${displayData.breakdown.project_relevance.percentage}%` }}
                          />
                        </div>
                      </div>

                      <div>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="font-semibold text-charcoal">Interview Depth & Proficiencies</span>
                          <span className="type-data text-xs font-bold text-orange">
                            {displayData.breakdown.interview_readiness.score.toFixed(1)} / {displayData.breakdown.interview_readiness.max} pts
                          </span>
                        </div>
                        <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-orange rounded-full"
                            style={{ width: `${displayData.breakdown.interview_readiness.percentage}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Matched vs Missing Skills Grid */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {/* Matched Skills */}
                    <div className="surface-card p-5 space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="type-micro text-success flex items-center gap-1.5">
                          <CheckCircle className="w-3.5 h-3.5" /> MATCHED SKILLS ({displayData.matched_skills.length})
                        </h4>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {displayData.matched_skills.map((s, idx) => (
                          <span
                            key={idx}
                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-success-light text-success font-medium text-xs rounded-md"
                          >
                            {s.name} · <span className="opacity-75 text-[10px] capitalize">{s.proficiency}</span>
                          </span>
                        ))}
                        {displayData.matched_skills.length === 0 && (
                          <span className="text-xs text-bronze-dark/40 italic">No direct matches found.</span>
                        )}
                      </div>
                    </div>

                    {/* Missing Skills */}
                    <div className="surface-card p-5 space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="type-micro text-warning flex items-center gap-1.5">
                          <AlertTriangle className="w-3.5 h-3.5" /> SKILLS TO PREPARE ({displayData.missing_skills.length})
                        </h4>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {displayData.missing_skills.map((s, idx) => (
                          <span
                            key={idx}
                            className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-md font-medium ${
                              s.importance === "required"
                                ? "bg-danger-light text-danger border border-danger/20"
                                : "bg-warning-light text-warning"
                            }`}
                          >
                            {s.skill}
                            <span className="text-[10px] opacity-75">({s.importance})</span>
                          </span>
                        ))}
                        {displayData.missing_skills.length === 0 && (
                          <span className="text-xs text-success font-medium">All required skills met!</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Highlights and Concern Areas */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    <div className="p-4 bg-success-light/40 border border-success/20 rounded-xl space-y-2">
                      <p className="font-bold text-success flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5" /> Fit Highlights
                      </p>
                      <ul className="space-y-1 text-charcoal/80 list-disc list-inside">
                        {displayData.fit_highlights.map((h, i) => (
                          <li key={i}>{h}</li>
                        ))}
                      </ul>
                    </div>

                    <div className="p-4 bg-warning-light/40 border border-warning/20 rounded-xl space-y-2">
                      <p className="font-bold text-warning flex items-center gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5" /> Preparation Watchouts
                      </p>
                      <ul className="space-y-1 text-charcoal/80 list-disc list-inside">
                        {displayData.concern_areas.map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  {/* Selection Process Rounds */}
                  {displayData.selection_rounds.length > 0 && (
                    <div className="surface-card p-5 space-y-3">
                      <h3 className="type-micro text-bronze-dark/70">RECRUITMENT SELECTION ROUNDS</h3>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        {displayData.selection_rounds.map((r, i) => (
                          <div key={i} className="p-3 bg-surface border border-border-subtle rounded-xl text-xs space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-charcoal">Round {r.round_number}</span>
                              <span className="text-[10px] text-bronze-dark/50">{r.duration_minutes}m</span>
                            </div>
                            <p className="font-semibold text-orange truncate">{r.name}</p>
                            <p className="text-bronze-dark/60 line-clamp-2">{r.description}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* ══════════════════════════════════════════════════
                  TAB 2: 2-WEEK ROADMAP
              ══════════════════════════════════════════════════ */}
              {activeTab === "roadmap" && (
                <div className="space-y-4 animate-fade-in">
                  <div className="p-4 surface-warm rounded-xl border border-border-default">
                    <h3 className="font-bold text-charcoal text-sm">Targeted Prep Plan for {job.company_name}</h3>
                    <p className="text-xs text-bronze-dark/60 mt-0.5">
                      Tailored specifically around the missing skills and interview rounds of this drive.
                    </p>
                  </div>

                  <div className="space-y-3">
                    {displayData.prep_roadmap.map((item, idx) => (
                      <div key={idx} className="surface-card p-4 flex items-start gap-4 hover-lift">
                        <div className="w-10 h-10 rounded-full bg-earth text-ivory flex items-center justify-center font-bold text-sm shrink-0">
                          W{item.week}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <h4 className="font-semibold text-charcoal text-sm">{item.focus_area}</h4>
                            <PBBadge variant={item.priority === "critical" ? "critical" : item.priority === "high" ? "high" : "medium"}>
                              {item.priority}
                            </PBBadge>
                          </div>
                          <p className="text-xs text-bronze-dark/70 mb-2 leading-relaxed">{item.action_item}</p>
                          <div className="flex items-center gap-3 text-xs text-bronze font-medium">
                            <span className="flex items-center gap-1 text-orange">
                              <BookOpen className="w-3.5 h-3.5" /> {item.resource}
                            </span>
                            <span className="text-bronze-dark/40">~{item.estimated_hours}h estimated</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ══════════════════════════════════════════════════
                  TAB 3: WHAT-IF SIMULATOR
              ══════════════════════════════════════════════════ */}
              {activeTab === "simulator" && (
                <div className="space-y-6 animate-fade-in">
                  <div className="p-4 bg-orange/8 border border-orange/20 rounded-xl space-y-1">
                    <h3 className="font-bold text-charcoal text-sm flex items-center gap-1.5">
                      <Zap className="w-4 h-4 text-orange" /> Interactive Preparedness Simulator
                    </h3>
                    <p className="text-xs text-bronze-dark/70">
                      See how your match score jumps if you master missing skills or solve more coding problems before the recruitment drive.
                    </p>
                  </div>

                  {/* Simulator Controls */}
                  <div className="surface-card p-5 space-y-4">
                    <h4 className="type-micro text-bronze-dark/70">1. SIMULATE CLOSING SKILL GAPS</h4>
                    <p className="text-xs text-bronze-dark/50">Select skills you plan to learn or refresh:</p>
                    
                    <div className="flex flex-wrap gap-2">
                      {data?.missing_skills?.map((s) => {
                        const isSelected = simulatedSkills.includes(s.skill);
                        return (
                          <button
                            key={s.skill}
                            type="button"
                            onClick={() => toggleSimulatedSkill(s.skill)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                              isSelected
                                ? "bg-orange text-white shadow-sm"
                                : "bg-surface-muted text-charcoal hover:bg-surface-warm border border-border-default"
                            }`}
                          >
                            <span>{isSelected ? "✓" : "+"}</span>
                            {s.skill} ({s.importance})
                          </button>
                        );
                      })}
                      {(!data?.missing_skills || data.missing_skills.length === 0) && (
                        <p className="text-xs text-success font-medium">No skill gaps to simulate!</p>
                      )}
                    </div>

                    <div className="pt-2">
                      <h4 className="type-micro text-bronze-dark/70 mb-2">2. SIMULATE CODING PRACTICE</h4>
                      <div className="flex items-center gap-4">
                        <input
                          type="range"
                          min="0"
                          max="100"
                          step="10"
                          value={additionalProblems}
                          onChange={(e) => setAdditionalProblems(parseInt(e.target.value))}
                          className="flex-1 accent-orange"
                        />
                        <span className="type-data text-sm font-bold text-charcoal w-24 text-right">
                          +{additionalProblems} problems
                        </span>
                      </div>
                    </div>

                    <div className="pt-3 border-t border-border-subtle flex justify-end">
                      <PBButton
                        variant="primary"
                        size="sm"
                        onClick={handleRunSimulation}
                        disabled={simulating}
                      >
                        {simulating ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Zap className="w-3.5 h-3.5 mr-1.5" />}
                        Recalculate Simulated Score
                      </PBButton>
                    </div>
                  </div>

                  {/* Simulation Result Comparison */}
                  {simulatedResult && data && (
                    <div className="surface-warm p-5 rounded-xl border border-orange/30 animate-fade-in space-y-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="type-micro text-orange font-bold">SIMULATION OUTCOME</p>
                          <h4 className="text-lg font-bold text-charcoal font-zodiak">
                            Score Jump: {data.match_percentage}% &rarr; {simulatedResult.match_percentage}%
                          </h4>
                        </div>
                        <span className="text-sm font-bold text-success bg-success-light px-3 py-1 rounded-full">
                          +{(simulatedResult.overall_score - data.overall_score).toFixed(1)} pts
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-3 text-xs">
                        <div className="p-3 bg-surface rounded-lg border border-border-subtle">
                          <p className="text-bronze-dark/50">Current Readiness</p>
                          <p className="text-base font-bold text-charcoal">{data.match_percentage}%</p>
                          <p className="text-[11px] text-bronze-dark/60">{data.match_tier}</p>
                        </div>
                        <div className="p-3 bg-surface rounded-lg border border-orange/40">
                          <p className="text-orange font-semibold">Simulated Readiness</p>
                          <p className="text-base font-bold text-orange">{simulatedResult.match_percentage}%</p>
                          <p className="text-[11px] text-success font-bold">{simulatedResult.match_tier}</p>
                        </div>
                      </div>

                      <p className="text-xs text-bronze-dark/70 italic text-center">
                        Closing {simulatedSkills.length} skills and solving {additionalProblems} problems lifts you into the top tier of candidates for {job.company_name}!
                      </p>
                    </div>
                  )}
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-border-subtle flex items-center justify-between bg-surface-warm/50 rounded-b-2xl">
          <p className="text-xs text-bronze-dark/50">
            Analysis calibrated with deterministic grading and recruitment benchmarks.
          </p>
          <PBButton variant="secondary" size="sm" onClick={onClose}>
            Done
          </PBButton>
        </div>
      </div>
    </div>
  );
}
