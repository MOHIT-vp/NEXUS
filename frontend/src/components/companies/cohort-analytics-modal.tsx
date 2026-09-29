"use client";

import { useEffect, useState } from "react";
import { X, CheckCircle, AlertTriangle, BarChart3, TrendingUp, Loader2 } from "lucide-react";
import { PBBadge } from "@/components/ui/pb-badge";
import { PBButton } from "@/components/ui/pb-button";
import { getCohortReadiness, CohortReadinessResult, JobDrive } from "@/lib/api";

interface CohortAnalyticsModalProps {
  job: JobDrive | null;
  isOpen: boolean;
  onClose: () => void;
}

export function CohortAnalyticsModal({ job, isOpen, onClose }: CohortAnalyticsModalProps) {
  const [data, setData] = useState<CohortReadinessResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !job) return;

    const fetchAnalytics = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await getCohortReadiness(job.job_id);
        setData(res);
      } catch (err: unknown) {
        console.error("Failed to load cohort readiness:", err);
        setError("Unable to compute cohort analytics. Please ensure students have completed evaluations.");
      } finally {
        setLoading(false);
      }
    };

    fetchAnalytics();
  }, [isOpen, job]);

  if (!isOpen || !job) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-charcoal/50 backdrop-blur-sm animate-fade-in overflow-y-auto">
      <div className="surface-card bg-ivory w-full max-w-2xl rounded-2xl shadow-xl border border-border-default my-8 flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-6 border-b border-border-subtle flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-orange/10 flex items-center justify-center text-orange">
              <BarChart3 className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-charcoal font-zodiak">{job.company_name}</h2>
                <PBBadge variant="medium">{job.role_family.replace("_", " ")}</PBBadge>
              </div>
              <p className="text-xs text-bronze-dark/50">Cohort Readiness & Candidate Pipeline Analytics</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-surface-muted text-bronze-dark/50 hover:text-charcoal transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {loading ? (
            <div className="py-12 flex flex-col items-center justify-center gap-3 text-bronze-dark/50">
              <Loader2 className="w-6 h-6 animate-spin text-orange" />
              <p className="text-sm font-medium">Aggregating batch readiness metrics...</p>
            </div>
          ) : error ? (
            <div className="p-4 bg-danger-light text-danger rounded-xl border border-danger/20 text-sm">
              {error}
            </div>
          ) : data ? (
            <>
              {/* Summary KPIs */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="surface-card p-4">
                  <p className="type-micro mb-1">Total Evaluated</p>
                  <p className="text-2xl font-bold text-charcoal">{data.total_students_evaluated}</p>
                  <p className="text-xs text-bronze-dark/40">Registered cohort</p>
                </div>
                <div className="surface-card p-4 border-t-2 border-t-success/60">
                  <p className="type-micro mb-1">Eligible Students</p>
                  <p className="text-2xl font-bold text-success">{data.eligible_percentage}%</p>
                  <p className="text-xs text-bronze-dark/40">{data.eligible_count} meet CGPA {job.min_cgpa}</p>
                </div>
                <div className="surface-card p-4">
                  <p className="type-micro mb-1">Avg Readiness</p>
                  <p className="text-2xl font-bold text-charcoal">{data.average_readiness_score}%</p>
                  <p className="text-xs text-bronze-dark/40">Across all metrics</p>
                </div>
                <div className="surface-card p-4 border-t-2 border-t-orange/60">
                  <p className="type-micro mb-1">Ready to Clear</p>
                  <p className="text-2xl font-bold text-orange">{data.high_fit_count}</p>
                  <p className="text-xs text-bronze-dark/40">Score &ge; 75%</p>
                </div>
              </div>

              {/* Fit Distribution */}
              <div className="surface-card p-5 space-y-3">
                <h3 className="type-micro text-bronze-dark/70">CANDIDATE FIT DISTRIBUTION</h3>
                <div className="space-y-2">
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="font-semibold text-success flex items-center gap-1.5">
                        <CheckCircle className="w-3.5 h-3.5" /> High Fit (&ge; 75%) — Immediate Candidates
                      </span>
                      <span className="font-bold text-charcoal">{data.high_fit_count} students</span>
                    </div>
                    <div className="h-2 bg-surface-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-success rounded-full"
                        style={{ width: `${(data.high_fit_count / data.total_students_evaluated) * 100}%` }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="font-semibold text-warning flex items-center gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5" /> Moderate Fit (55% - 74%) — Minor Skill Gaps
                      </span>
                      <span className="font-bold text-charcoal">{data.moderate_fit_count} students</span>
                    </div>
                    <div className="h-2 bg-surface-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-warning rounded-full"
                        style={{ width: `${(data.moderate_fit_count / data.total_students_evaluated) * 100}%` }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="font-semibold text-bronze-dark/70 flex items-center gap-1.5">
                        <TrendingUp className="w-3.5 h-3.5" /> Preparation Needed (&lt; 55%) — Foundational Gaps
                      </span>
                      <span className="font-bold text-charcoal">{data.low_fit_count} students</span>
                    </div>
                    <div className="h-2 bg-surface-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-bronze/40 rounded-full"
                        style={{ width: `${(data.low_fit_count / data.total_students_evaluated) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Common Missing Skills for Placement Cell Bootcamps */}
              <div className="surface-card p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="type-micro text-bronze-dark/70">CAMPUS SKILL GAPS FOR THIS DRIVE</h3>
                    <p className="text-xs text-bronze-dark/50">Identify what training or mock tests to organize prior to {job.drive_date || "the drive"}.</p>
                  </div>
                </div>

                <div className="space-y-3 pt-1">
                  {data.common_missing_skills.length === 0 ? (
                    <p className="text-xs text-success font-semibold py-2">
                      All required skills are fully covered across registered students!
                    </p>
                  ) : (
                    data.common_missing_skills.map((item, idx) => (
                      <div key={idx} className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span className="font-semibold text-charcoal">{item.skill}</span>
                          <span className="text-bronze-dark/60 font-medium">
                            Missing in {item.missing_count} students ({item.missing_percentage}%)
                          </span>
                        </div>
                        <div className="h-2 bg-surface-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-orange/80 rounded-full"
                            style={{ width: `${item.missing_percentage}%` }}
                          />
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Criteria Summary */}
              <div className="p-4 bg-surface-warm/60 rounded-xl text-xs space-y-1.5 border border-border-subtle">
                <p className="font-semibold text-charcoal">Recruitment Criteria Overview:</p>
                <div className="grid grid-cols-2 gap-2 text-bronze-dark/70">
                  <div>· Min CGPA: <span className="font-medium text-charcoal">{job.min_cgpa}</span></div>
                  <div>· CTC / Package: <span className="font-medium text-charcoal">₹{job.package_lpa} LPA</span></div>
                  <div>· Drive Date: <span className="font-medium text-charcoal">{job.drive_date || "To be announced"}</span></div>
                  <div>· Mandatory Skills: <span className="font-medium text-charcoal">{job.required_skills.join(", ") || "None"}</span></div>
                </div>
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-border-subtle flex justify-end bg-surface-warm/50 rounded-b-2xl">
          <PBButton variant="primary" size="sm" onClick={onClose}>
            Close Analytics
          </PBButton>
        </div>
      </div>
    </div>
  );
}
