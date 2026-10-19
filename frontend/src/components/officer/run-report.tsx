"use client";

import { PBBadge } from "@/components/ui/pb-badge";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Report = { result_snapshot?: any; validation_report?: any };

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-bronze-dark/50">{title}</h4>
      {children}
    </div>
  );
}

/** The assembled plan an officer reviews before approving (doc 9.9). */
export function RunReport({ report }: { report: Report }) {
  const s = report.result_snapshot || {};
  const summary = s.summary || {};
  const gaps: any[] = s.skill_gap_report?.gaps || [];
  const matches: any[] = s.matching_result?.matches || [];
  const roadmap: any[] = s.roadmap?.items || [];
  const sessions: any[] = s.interview_result?.mock_interview_plan?.sessions || [];
  const coding = s.coding_analytics?.summary || {};
  const sources: any[] = s.coding_analytics?.sources || [];
  const checks: any[] = report.validation_report?.checks || s.validation_report?.checks || [];

  return (
    <div className="w-full mt-3 rounded-[12px] border border-border-subtle bg-ivory p-4 grid md:grid-cols-2 gap-5 text-sm">
      <Section title="Readiness">
        <p className="text-charcoal">
          Readiness <b>{summary.readiness_percentage ?? "—"}%</b> · skill coverage <b>{summary.skill_coverage ?? "—"}%</b> ·
          {" "}{summary.evidence_count ?? s.evidence_count ?? 0} evidence records
        </p>
        <p className="text-bronze-dark/60 text-xs">
          Coding: {sources.length ? sources.map((x) => `${x.source} ${x.status}`).join(", ") : "no platform data"}
          {coding.total_solved != null && ` · ${coding.total_solved} problems solved (LeetCode)`}
        </p>
      </Section>

      <Section title={`Skill gaps (${gaps.length})`}>
        {gaps.slice(0, 6).map((g) => (
          <p key={g.skill} className="text-charcoal">
            <PBBadge variant={g.severity === "critical" ? "critical" : g.severity === "high" ? "high" : "low"}>{g.severity}</PBBadge>{" "}
            {g.skill}: {g.current_level} → {g.required_level}
            <span className="text-bronze-dark/50 text-xs"> · {g.benchmark_source || "benchmark"}</span>
          </p>
        ))}
        {gaps.length === 0 && <p className="text-bronze-dark/50">No gaps found.</p>}
      </Section>

      <Section title={`Company matches (${matches.length})`}>
        {matches.slice(0, 5).map((m) => (
          <div key={m.job_id}>
            <p className="text-charcoal">
              {m.company_name} — {m.role_title}: <b>{m.match_percentage}%</b>
              <span className="text-xs text-bronze-dark/50"> · confidence {Math.round((m.confidence ?? 0) * 100)}%{m.is_eligible ? "" : " · not eligible"}</span>
              {m.is_low_confidence && <> <PBBadge variant="high">Low confidence — review</PBBadge></>}
            </p>
            <p className="text-xs text-bronze-dark/60">{m.reasoning}</p>
          </div>
        ))}
        {matches.length === 0 && <p className="text-bronze-dark/50">No open drives to match.</p>}
      </Section>

      <Section title="Roadmap & mock interviews">
        {s.roadmap?.selection && (
          <p className="text-xs text-bronze-dark/60">
            Best of {s.roadmap.selection.candidates.length} candidate roadmaps:{" "}
            <b className="text-charcoal">{String(s.roadmap.selection.selected).replace(/_/g, " ")}</b>{" "}
            (plan fit {s.roadmap.selection.score}/100)
          </p>
        )}
        {roadmap.slice(0, 4).map((r, i) => (
          <p key={i} className="text-charcoal">• {r.title}{r.resources?.[0] ? <span className="text-xs text-bronze-dark/50"> · {r.resources[0].title}</span> : null}</p>
        ))}
        {sessions.slice(0, 3).map((x) => (
          <p key={x.session} className="text-xs text-bronze-dark/60">Week {x.week}: {x.type} mock interview on {x.focus}</p>
        ))}
      </Section>

      {(s.officer_notes || []).length > 0 && (
        <Section title="Officer notes">
          {s.officer_notes.map((n: any, i: number) => <p key={i} className="text-charcoal">{n.note} <span className="text-xs text-bronze-dark/50">— {n.by}</span></p>)}
        </Section>
      )}

      <Section title={`Validation (${checks.filter((c) => c.passed).length}/${checks.length} passed)`}>
        {checks.filter((c) => !c.passed).map((c) => (
          <p key={c.code} className={c.severity === "error" ? "text-danger" : "text-warning"}>✗ {c.name}: {c.message}</p>
        ))}
        {checks.length > 0 && checks.every((c) => c.passed) && <p className="text-success">All checks passed.</p>}
      </Section>
    </div>
  );
}
