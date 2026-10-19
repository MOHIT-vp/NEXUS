"use client";

import { ChevronRight, Download, ExternalLink, Flag, Rocket, Target, TrendingUp, Trophy } from "lucide-react";
import { PBButton } from "@/components/ui/pb-button";

export type RoadmapStep = {
  skill: string;
  action: string;
  resource: string;
  resource_url?: string | null;
  estimated_hours: number;
  priority: string;
  current_level?: string | null;
  target_level?: string | null;
  importance?: string | null;
  milestone?: string | null;
};

export type RoadmapMeta = { timeline?: string | null; timeline_weeks?: number | null; total_hours?: number | null };

const PHASES = [
  { key: 1, title: "Must-have foundations", blurb: "Skills your target role requires and you don't show yet. Start here.", icon: Target },
  { key: 2, title: "Level up", blurb: "Skills you have — take them to the level companies expect.", icon: TrendingUp },
  { key: 3, title: "Bonus edge", blurb: "Preferred skills that make you stand out once the basics are solid.", icon: Rocket },
] as const;

const PRIORITY_STYLE: Record<string, string> = {
  critical: "bg-danger-light text-danger border-danger/20",
  high: "bg-warning-light text-warning border-warning/20",
  medium: "bg-ivory-warm text-bronze-dark border-bronze/15",
  low: "bg-surface-muted text-bronze-dark/60 border-border-subtle",
};

function phaseOf(s: RoadmapStep): 1 | 2 | 3 {
  if (s.importance === "preferred" || s.importance === "nice_to_have") return 3;
  const missing = !s.current_level || s.current_level === "missing";
  if (missing && (s.priority === "critical" || s.priority === "high")) return 1;
  if (!s.importance && (s.priority === "critical" || s.priority === "high")) return 1;
  return 2;
}

const cap = (v?: string | null) => (v ? v.charAt(0).toUpperCase() + v.slice(1) : "");
const weekRange = (a: number, b: number) => (a === b ? `Week ${a}` : `Week ${a} – Week ${b}`);

type Phase = (typeof PHASES)[number] & { steps: RoadmapStep[] };
type ScheduledStep = RoadmapStep & { n: number; start: number; end: number };

/** Spread the steps over the plan's timeline (weeks), in order. */
function schedule(phases: Phase[], totalWeeks: number) {
  const totalEffort = phases.reduce((n, p) => n + p.steps.reduce((m, s) => m + (s.estimated_hours || 1), 0), 0) || 1;
  const perWeek = totalEffort / totalWeeks;
  const out: (Omit<Phase, "steps"> & { start: number; end: number; steps: ScheduledStep[] })[] = [];
  let done = 0;
  let n = 0;
  for (const p of phases) {
    const steps: ScheduledStep[] = [];
    for (const s of p.steps) {
      const start = Math.min(totalWeeks, Math.floor(done / perWeek) + 1);
      done += s.estimated_hours || 1;
      const end = Math.min(totalWeeks, Math.max(start, Math.ceil(done / perWeek)));
      n += 1;
      steps.push({ ...s, n, start, end });
    }
    out.push({ ...p, steps, start: steps[0].start, end: steps[steps.length - 1].end });
  }
  return out;
}

function StepCard({ s }: { s: ScheduledStep }) {
  return (
    <div className="surface-card p-5 hover-lift">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-2 flex-wrap">
          <h4 className="font-semibold text-charcoal">{s.skill}</h4>
          <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${PRIORITY_STYLE[s.priority] || PRIORITY_STYLE.low}`}>
            {cap(s.priority)}
          </span>
        </div>
        <span className="text-xs font-semibold text-orange bg-orange/8 border border-orange/15 rounded-full px-2.5 py-0.5">
          {weekRange(s.start, s.end)}
        </span>
      </div>
      <p className="text-sm text-bronze-dark/70">{s.action}</p>

      {s.milestone && s.milestone !== s.action && (
        <p className="mt-3 text-sm text-charcoal flex items-start gap-2">
          <Flag className="w-4 h-4 text-success shrink-0 mt-0.5" />
          <span><span className="font-medium">Done when:</span> {s.milestone}</span>
        </p>
      )}

      <div className="mt-3 pt-3 border-t border-border-subtle">
        {s.resource_url ? (
          <a href={s.resource_url} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-orange hover:underline">
            {s.resource} <ExternalLink className="w-3.5 h-3.5" />
          </a>
        ) : (
          <span className="text-sm text-bronze-dark/60">{s.resource}</span>
        )}
      </div>
    </div>
  );
}

export function RoadmapPath({ steps, meta, onDownload }: { steps: RoadmapStep[]; meta?: RoadmapMeta; onDownload: () => void }) {
  const totalWeeks = Math.max(1, meta?.timeline_weeks || Math.ceil(steps.length / 2));
  const grouped = PHASES.map((p) => ({ ...p, steps: steps.filter((s) => phaseOf(s) === p.key) })).filter((p) => p.steps.length);
  const scheduled = schedule(grouped, totalWeeks);
  const lastPhase = scheduled.length - 1;

  return (
    <div className="space-y-8">
      {/* Overview */}
      <div className="surface-card p-6">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-6">
          <div>
            <h2 className="type-h2 mb-1">Your learning roadmap</h2>
            <p className="type-body text-bronze-dark/60">
              {steps.length} steps · {weekRange(1, totalWeeks)}{meta?.timeline ? ` (${meta.timeline})` : ""}
            </p>
          </div>
          <PBButton variant="secondary" size="sm" onClick={onDownload}>
            <Download className="w-4 h-4" /> Download
          </PBButton>
        </div>

        {/* Phase strip: the route at a glance */}
        <div className="flex flex-col sm:flex-row sm:items-stretch gap-2">
          {scheduled.map((p, i) => (
            <div key={p.key} className="contents">
              <a href={`#phase-${p.key}`}
                className="flex-1 rounded-[14px] border border-border-subtle bg-ivory p-4 hover:border-orange/40 transition-colors">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="w-6 h-6 rounded-full bg-earth text-ivory text-xs font-bold flex items-center justify-center">{i + 1}</span>
                  <span className="font-semibold text-charcoal text-sm">{p.title}</span>
                </div>
                <p className="text-xs text-bronze-dark/60">
                  {p.steps.length} step{p.steps.length > 1 ? "s" : ""} · <span className="font-semibold text-orange">{weekRange(p.start, p.end)}</span>
                </p>
              </a>
              {i < scheduled.length - 1 && (
                <div className="hidden sm:flex items-center justify-center shrink-0 w-5" aria-hidden>
                  <ChevronRight className="w-4 h-4 text-bronze-dark/30" />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Phases with steps on a connected path */}
      {scheduled.map((p, pi) => (
        <section key={p.key} id={`phase-${p.key}`} className="scroll-mt-24">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-[12px] bg-orange flex items-center justify-center">
              <p.icon className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="font-semibold text-lg text-charcoal">
                Phase {pi + 1} · {p.title}
                <span className="ml-2 text-sm font-medium text-orange">{weekRange(p.start, p.end)}</span>
              </h3>
              <p className="text-sm text-bronze-dark/60">{p.blurb}</p>
            </div>
          </div>

          <ol className="space-y-4">
            {p.steps.map((s, si) => {
              // The path runs from each step to the next; in the last phase the final step leads to the finish
              const connects = si < p.steps.length - 1 || pi === lastPhase;
              return (
                <li key={s.n} className="relative pl-14">
                  {connects && (
                    <span className="absolute left-[19px] top-[52px] -bottom-4 border-l-2 border-dashed border-bronze/25" aria-hidden />
                  )}
                  <span className="absolute left-1 top-5 w-8 h-8 rounded-full bg-surface border-2 border-orange text-orange text-sm font-bold flex items-center justify-center">
                    {s.n}
                  </span>
                  <StepCard s={s} />
                </li>
              );
            })}
            {pi === lastPhase && (
              <li className="relative pl-14">
                <span className="absolute left-1 top-4 w-8 h-8 rounded-full bg-success text-white flex items-center justify-center">
                  <Trophy className="w-4 h-4" />
                </span>
                <div className="surface-card p-5 border-success/30 bg-success-light/40">
                  <p className="text-sm text-charcoal">
                    <span className="font-semibold">Finish line:</span> every step done means your profile meets your target role&apos;s
                    requirements — re-analyse your resume to update your readiness score.
                  </p>
                </div>
              </li>
            )}
          </ol>
        </section>
      ))}
    </div>
  );
}
