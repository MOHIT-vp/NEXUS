"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Code2,
  Play,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ChevronRight,
  ArrowLeft,
  Loader2,
  RotateCcw,
  Terminal,
  Zap,
  CheckCircle2,
  Sparkles,
} from "lucide-react";
import { PBButton } from "@/components/ui/pb-button";
import { PBBadge } from "@/components/ui/pb-badge";
import {
  listCodingProblems,
  submitCodingSolution,
  runCodingSolution,
  CodingProblem,
  SubmissionResult,
} from "@/lib/api";

const STORAGE_KEY_SOLVED = "placement_coding_solved_problems";
const STORAGE_KEY_DRAFTS = "placement_coding_drafts_v1";

function getStoredSolvedIds(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY_SOLVED);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveSolvedId(id: string) {
  if (typeof window === "undefined") return;
  try {
    const current = getStoredSolvedIds();
    if (!current.includes(id)) {
      const updated = [...current, id];
      localStorage.setItem(STORAGE_KEY_SOLVED, JSON.stringify(updated));
    }
  } catch {
    // ignore
  }
}

function getStoredDrafts(): Record<string, string> {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY_DRAFTS);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveDraft(problemId: string, code: string) {
  if (typeof window === "undefined") return;
  try {
    const drafts = getStoredDrafts();
    drafts[problemId] = code;
    localStorage.setItem(STORAGE_KEY_DRAFTS, JSON.stringify(drafts));
  } catch {
    // ignore
  }
}

function clearDraft(problemId: string) {
  if (typeof window === "undefined") return;
  try {
    const drafts = getStoredDrafts();
    delete drafts[problemId];
    localStorage.setItem(STORAGE_KEY_DRAFTS, JSON.stringify(drafts));
  } catch {
    // ignore
  }
}

/* ───────────────────────────────────────────────────────────── */
/*  Problem List View                                            */
/* ───────────────────────────────────────────────────────────── */

function ProblemList({
  problems,
  solvedIds,
  onSelect,
}: {
  problems: CodingProblem[];
  solvedIds: string[];
  onSelect: (p: CodingProblem) => void;
}) {
  const solvedCount = problems.filter((p) => solvedIds.includes(p.id)).length;
  const progressPct = problems.length > 0 ? (solvedCount / problems.length) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Banner / Header */}
      <div className="surface-card p-6 border border-border-default rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-1 max-w-xl">
          <div className="flex items-center gap-2">
            <h2 className="type-h2">Coding Practice</h2>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-orange/10 text-orange">
              <Zap className="w-3 h-3" />
              LeetCode Style
            </span>
          </div>
          <p className="type-body text-bronze-dark/60 text-sm">
            Solve 3 curated technical interview coding challenges. Type code, test against
            live sample test cases, and submit to verify against complete test suites.
            Evaluated in an isolated Python 3 sandbox.
          </p>
        </div>

        {/* Solved Progress Box */}
        <div className="bg-surface-muted/60 border border-border-default/60 rounded-xl p-4 min-w-[200px] shrink-0">
          <div className="flex items-center justify-between text-xs mb-1.5">
            <span className="font-semibold text-charcoal flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-orange" />
              Progress
            </span>
            <span className="font-bold text-orange">
              {solvedCount} / {problems.length} Solved
            </span>
          </div>
          <div className="h-2 bg-border-default/50 rounded-full overflow-hidden mb-1">
            <div
              className="h-full bg-orange rounded-full transition-all duration-500"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <p className="text-[11px] text-bronze-dark/50">
            {solvedCount === problems.length
              ? "All challenges completed! 🎉"
              : `${problems.length - solvedCount} remaining to solve`}
          </p>
        </div>
      </div>

      {/* Problem Cards */}
      <div className="grid gap-3">
        {problems.map((p, idx) => {
          const isSolved = solvedIds.includes(p.id);
          const isMedium = p.difficulty.toLowerCase() === "medium";

          return (
            <button
              key={p.id}
              onClick={() => onSelect(p)}
              className="surface-card p-5 text-left hover:border-orange/50 border border-border-default rounded-2xl transition-all hover-lift flex items-center justify-between gap-4 group"
            >
              <div className="flex items-center gap-4 min-w-0">
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm shrink-0 transition-colors ${
                    isSolved
                      ? "bg-success-light text-success"
                      : "bg-surface-muted text-charcoal-light group-hover:bg-orange/10 group-hover:text-orange"
                  }`}
                >
                  {isSolved ? <CheckCircle2 className="w-5 h-5 text-success" /> : idx + 1}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-bold text-charcoal text-base font-zodiak leading-tight">
                      {p.title}
                    </h3>
                    <PBBadge variant={isMedium ? "medium" : "success"}>
                      {p.difficulty}
                    </PBBadge>
                    {isSolved && (
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-success bg-success-light px-2 py-0.5 rounded-full border border-success/20">
                        <CheckCircle className="w-3 h-3" />
                        Solved
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-bronze-dark/50 mt-1 flex items-center gap-3">
                    <span>{p.test_count} test cases</span>
                    <span>·</span>
                    <span>
                      Function: <code className="text-orange font-mono font-medium">{p.function_name}()</code>
                    </span>
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <span className="text-xs font-semibold text-orange hidden sm:inline-block group-hover:translate-x-0.5 transition-transform">
                  {isSolved ? "Review Code" : "Solve Challenge"} &rarr;
                </span>
                <ChevronRight className="w-4 h-4 text-bronze-dark/40 group-hover:text-orange transition-colors" />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ───────────────────────────────────────────────────────────── */
/*  Code Editor Component with Smart Indent & Shortcuts         */
/* ───────────────────────────────────────────────────────────── */

function CodeEditor({
  value,
  onChange,
  onRun,
  onSubmit,
}: {
  value: string;
  onChange: (v: string) => void;
  onRun?: () => void;
  onSubmit?: () => void;
}) {
  const lines = value.split("\n");

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const target = e.currentTarget;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      const newValue = value.substring(0, start) + "    " + value.substring(end);
      onChange(newValue);
      requestAnimationFrame(() => {
        target.selectionStart = target.selectionEnd = start + 4;
      });
    } else if (e.key === "Enter") {
      // Shortcuts: Ctrl+Shift+Enter = Submit, Ctrl+Enter = Run
      if ((e.ctrlKey || e.metaKey) && e.shiftKey) {
        e.preventDefault();
        onSubmit?.();
        return;
      }
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        onRun?.();
        return;
      }

      // Smart Python Auto-Indentation
      e.preventDefault();
      const target = e.currentTarget;
      const start = target.selectionStart;
      const end = target.selectionEnd;

      const beforeCursor = value.substring(0, start);
      const afterCursor = value.substring(end);
      const lastNewline = beforeCursor.lastIndexOf("\n");
      const currentLine = beforeCursor.substring(lastNewline + 1);

      // Extract leading spaces/tabs
      const match = currentLine.match(/^[ \t]*/);
      let indent = match ? match[0] : "";

      // If line ends with a colon, add 4 additional spaces
      if (currentLine.trimEnd().endsWith(":")) {
        indent += "    ";
      }

      const insertion = "\n" + indent;
      const newValue = beforeCursor + insertion + afterCursor;
      onChange(newValue);

      requestAnimationFrame(() => {
        target.selectionStart = target.selectionEnd = start + insertion.length;
      });
    }
  };

  return (
    <div className="relative border border-border-default rounded-xl overflow-hidden bg-[#181825] shadow-inner">
      <div className="flex text-sm font-mono">
        {/* Line numbers */}
        <div className="select-none py-3 px-3 text-right border-r border-white/10 bg-[#11111b] text-white/25 leading-[1.625rem]">
          {lines.map((_, i) => (
            <div key={i} className="text-xs font-mono">
              {i + 1}
            </div>
          ))}
        </div>
        {/* Code area */}
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          spellCheck={false}
          className="flex-1 bg-transparent text-[#cdd6f4] font-mono text-sm leading-[1.625rem] p-3 resize-none focus:outline-none min-h-[340px] placeholder:text-white/20 selection:bg-orange/30"
          placeholder="Write your Python 3 solution here..."
        />
      </div>
    </div>
  );
}

/* ───────────────────────────────────────────────────────────── */
/*  Results Panel Component                                      */
/* ───────────────────────────────────────────────────────────── */

function ResultsPanel({
  result,
  mode,
}: {
  result: SubmissionResult;
  mode: "run" | "submit";
}) {
  const [activeTab, setActiveTab] = useState<"tests" | "console">("tests");
  const [selectedCaseIdx, setSelectedCaseIdx] = useState(0);

  const selectedCase = result.results[selectedCaseIdx] || result.results[0];

  // Consolidate console outputs
  const allConsoleOutput = result.results
    .map((r, i) => {
      if (r.console_output && r.console_output.trim()) {
        return `[Test Case ${i + 1}]\n${r.console_output.trim()}`;
      }
      return "";
    })
    .filter(Boolean)
    .join("\n\n");

  const hasConsoleOutput = Boolean(allConsoleOutput.trim());

  return (
    <div className="space-y-4 pt-2">
      {/* Status Banner */}
      <div
        className={`p-4 rounded-xl border flex items-center justify-between gap-4 ${
          result.all_passed
            ? "bg-success-light/80 border-success/30 text-success"
            : "bg-danger-light/80 border-danger/30 text-danger"
        }`}
      >
        <div className="flex items-center gap-3">
          {result.all_passed ? (
            <CheckCircle className="w-5 h-5 text-success shrink-0" />
          ) : (
            <XCircle className="w-5 h-5 text-danger shrink-0" />
          )}
          <div>
            <h4 className="font-bold text-sm leading-tight">
              {result.all_passed
                ? mode === "submit"
                  ? "Accepted! All test cases passed 🎉"
                  : "Sample Test Cases Passed! Ready to Submit."
                : `${result.passed_count}/${result.total_count} Test Cases Passed`}
            </h4>
            <p className="text-xs opacity-80 mt-0.5">
              {mode === "submit"
                ? `Full evaluation against ${result.total_count} test cases`
                : `Sample evaluation against ${result.total_count} test cases`}
            </p>
          </div>
        </div>

        {result.total_execution_time_ms !== undefined && (
          <div className="flex items-center gap-1.5 text-xs font-mono font-semibold px-2.5 py-1 rounded-lg bg-surface/60 border border-current/10 shrink-0">
            <Zap className="w-3.5 h-3.5" />
            <span>{result.total_execution_time_ms.toFixed(1)} ms</span>
          </div>
        )}
      </div>

      {/* Result Tabs (Test Cases vs Console Output) */}
      <div className="border border-border-default rounded-xl bg-surface overflow-hidden">
        <div className="flex items-center justify-between border-b border-border-default px-4 bg-surface-muted/40">
          <div className="flex items-center gap-1">
            <button
              onClick={() => setActiveTab("tests")}
              className={`px-3 py-2 text-xs font-semibold border-b-2 transition-colors ${
                activeTab === "tests"
                  ? "border-orange text-orange font-bold"
                  : "border-transparent text-bronze-dark/60 hover:text-charcoal"
              }`}
            >
              Test Cases ({result.passed_count}/{result.total_count})
            </button>
            <button
              onClick={() => setActiveTab("console")}
              className={`px-3 py-2 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
                activeTab === "console"
                  ? "border-orange text-orange font-bold"
                  : "border-transparent text-bronze-dark/60 hover:text-charcoal"
              }`}
            >
              <Terminal className="w-3.5 h-3.5" />
              Console Output
              {hasConsoleOutput && (
                <span className="w-2 h-2 rounded-full bg-orange animate-pulse" />
              )}
            </button>
          </div>
        </div>

        {/* Tab 1: Test Cases */}
        {activeTab === "tests" && (
          <div className="p-4 space-y-4">
            {/* Case selector pills */}
            <div className="flex items-center gap-2 flex-wrap">
              {result.results.map((tc, idx) => {
                const isSelected = idx === selectedCaseIdx;
                return (
                  <button
                    key={tc.test_case}
                    onClick={() => setSelectedCaseIdx(idx)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border ${
                      isSelected
                        ? tc.passed
                          ? "bg-success-light border-success text-success font-semibold"
                          : "bg-danger-light border-danger text-danger font-semibold"
                        : tc.passed
                        ? "bg-surface border-border-default text-success/90 hover:bg-success-light/40"
                        : "bg-surface border-border-default text-danger/90 hover:bg-danger-light/40"
                    }`}
                  >
                    {tc.passed ? (
                      <CheckCircle className="w-3 h-3 text-success" />
                    ) : (
                      <XCircle className="w-3 h-3 text-danger" />
                    )}
                    Case {tc.test_case}
                  </button>
                );
              })}
            </div>

            {/* Selected case breakdown */}
            {selectedCase && (
              <div className="p-4 rounded-xl bg-surface-muted/50 border border-border-default/80 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-charcoal">
                    Test Case {selectedCase.test_case} Details
                  </span>
                  {selectedCase.execution_time_ms !== undefined && (
                    <span className="text-bronze-dark/50 font-mono text-[11px]">
                      {selectedCase.execution_time_ms.toFixed(1)} ms
                    </span>
                  )}
                </div>

                {/* Input arguments */}
                {selectedCase.input && (
                  <div>
                    <span className="text-[11px] font-semibold text-bronze-dark/60 uppercase tracking-wider block mb-1">
                      Input
                    </span>
                    <pre className="p-2.5 rounded-lg bg-surface border border-border-default text-xs font-mono text-charcoal overflow-x-auto">
                      {Object.entries(selectedCase.input)
                        .map(([k, v]) => `${k} = ${JSON.stringify(v)}`)
                        .join(", ")}
                    </pre>
                  </div>
                )}

                {/* Expected vs Actual */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <span className="text-[11px] font-semibold text-bronze-dark/60 uppercase tracking-wider block mb-1">
                      Expected Output
                    </span>
                    <pre className="p-2.5 rounded-lg bg-surface border border-border-default text-xs font-mono text-charcoal overflow-x-auto">
                      {JSON.stringify(selectedCase.expected)}
                    </pre>
                  </div>
                  <div>
                    <span className="text-[11px] font-semibold text-bronze-dark/60 uppercase tracking-wider block mb-1">
                      Your Output
                    </span>
                    <pre
                      className={`p-2.5 rounded-lg border text-xs font-mono overflow-x-auto ${
                        selectedCase.passed
                          ? "bg-surface border-success/30 text-success"
                          : "bg-surface border-danger/30 text-danger"
                      }`}
                    >
                      {selectedCase.actual !== null && selectedCase.actual !== undefined
                        ? JSON.stringify(selectedCase.actual)
                        : selectedCase.error
                        ? `Error: ${selectedCase.error}`
                        : "None"}
                    </pre>
                  </div>
                </div>

                {/* Error message */}
                {selectedCase.error && (
                  <div className="p-3 bg-danger-light border border-danger/20 rounded-lg text-xs font-mono text-danger whitespace-pre-wrap break-all">
                    {selectedCase.error}
                  </div>
                )}

                {/* Per-case console output if any */}
                {selectedCase.console_output && selectedCase.console_output.trim() && (
                  <div>
                    <span className="text-[11px] font-semibold text-bronze-dark/60 uppercase tracking-wider block mb-1">
                      Stdout
                    </span>
                    <pre className="p-2.5 rounded-lg bg-[#181825] border border-border-default text-xs font-mono text-[#cdd6f4] overflow-x-auto whitespace-pre-wrap">
                      {selectedCase.console_output}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Console Output */}
        {activeTab === "console" && (
          <div className="p-4">
            {hasConsoleOutput ? (
              <pre className="p-4 rounded-xl bg-[#181825] text-[#cdd6f4] font-mono text-xs leading-relaxed whitespace-pre-wrap overflow-x-auto max-h-64 border border-white/5">
                {allConsoleOutput}
              </pre>
            ) : (
              <div className="py-8 text-center text-xs text-bronze-dark/40 font-mono">
                No print() console output produced during this run.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ───────────────────────────────────────────────────────────── */
/*  Problem Workspace Component                                  */
/* ───────────────────────────────────────────────────────────── */

function ProblemWorkspace({
  problem,
  isSolved,
  onBack,
  onProblemSolved,
}: {
  problem: CodingProblem;
  isSolved: boolean;
  onBack: () => void;
  onProblemSolved: (id: string) => void;
}) {
  const [code, setCode] = useState(() => {
    const drafts = getStoredDrafts();
    return drafts[problem.id] ?? problem.starter_code;
  });
  const [running, setRunning] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SubmissionResult | null>(null);
  const [executionMode, setExecutionMode] = useState<"run" | "submit">("submit");
  const [apiError, setApiError] = useState<string | null>(null);

  const handleCodeChange = (newCode: string) => {
    setCode(newCode);
    saveDraft(problem.id, newCode);
  };

  const handleReset = () => {
    clearDraft(problem.id);
    setCode(problem.starter_code);
    setResult(null);
    setApiError(null);
  };

  const handleRun = useCallback(async () => {
    if (running || submitting || !code.trim()) return;
    setRunning(true);
    setResult(null);
    setApiError(null);
    setExecutionMode("run");

    try {
      const res = await runCodingSolution(problem.id, code);
      setResult(res);
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Run failed");
    } finally {
      setRunning(false);
    }
  }, [problem.id, code, running, submitting]);

  const handleSubmit = useCallback(async () => {
    if (running || submitting || !code.trim()) return;
    setSubmitting(true);
    setResult(null);
    setApiError(null);
    setExecutionMode("submit");

    try {
      const res = await submitCodingSolution(problem.id, code, "submit");
      setResult(res);
      if (res.all_passed) {
        onProblemSolved(problem.id);
      }
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }, [problem.id, code, running, submitting, onProblemSolved]);

  const isMedium = problem.difficulty.toLowerCase() === "medium";

  return (
    <div className="space-y-6">
      {/* Top bar */}
      <div className="flex items-center justify-between gap-4 flex-wrap pb-2 border-b border-border-default/60">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="w-9 h-9 rounded-xl bg-surface-muted flex items-center justify-center text-bronze-dark/70 hover:text-charcoal hover:bg-border-default/40 transition-colors shrink-0"
            title="Back to all problems"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="type-h2">{problem.title}</h2>
              <PBBadge variant={isMedium ? "medium" : "success"}>
                {problem.difficulty}
              </PBBadge>
              {isSolved && (
                <span className="inline-flex items-center gap-1 text-xs font-semibold text-success bg-success-light px-2.5 py-0.5 rounded-full border border-success/20">
                  <CheckCircle className="w-3.5 h-3.5" />
                  Solved
                </span>
              )}
            </div>
            <p className="text-xs text-bronze-dark/50 mt-0.5">
              {problem.test_count} test cases · Python 3 Environment
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-bronze-dark/50">
          <span className="hidden sm:inline">Shortcuts:</span>
          <kbd className="px-2 py-0.5 bg-surface-muted border border-border-default rounded text-[11px] font-mono text-charcoal">
            Ctrl+Enter
          </kbd>
          <span className="hidden sm:inline">Run ·</span>
          <kbd className="px-2 py-0.5 bg-surface-muted border border-border-default rounded text-[11px] font-mono text-charcoal">
            Ctrl+Shift+Enter
          </kbd>
          <span className="hidden sm:inline">Submit</span>
        </div>
      </div>

      {/* Main Split Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left column: Problem Details (5 cols) */}
        <div className="lg:col-span-5 surface-card p-6 space-y-6 overflow-y-auto max-h-[75vh] border border-border-default rounded-2xl">
          {/* Description */}
          <div>
            <h3 className="type-micro mb-2 text-bronze-dark/50">DESCRIPTION</h3>
            <div className="prose prose-sm text-bronze-dark/80 leading-relaxed whitespace-pre-wrap font-sans text-sm">
              {problem.description}
            </div>
          </div>

          {/* Examples */}
          <div>
            <h3 className="type-micro mb-3 text-bronze-dark/50">EXAMPLES</h3>
            <div className="space-y-3">
              {problem.examples.map((ex, i) => (
                <div
                  key={i}
                  className="p-3.5 bg-surface-muted/60 border border-border-default/70 rounded-xl text-xs space-y-1.5 font-mono"
                >
                  <p>
                    <span className="font-semibold text-charcoal">Input:</span>{" "}
                    <span className="text-bronze-dark/80">{ex.input}</span>
                  </p>
                  <p>
                    <span className="font-semibold text-charcoal">Output:</span>{" "}
                    <span className="text-orange font-bold">{ex.output}</span>
                  </p>
                  {ex.explanation && (
                    <p className="text-[11px] text-bronze-dark/60 font-sans italic pt-1 border-t border-border-default/40">
                      {ex.explanation}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Constraints */}
          {problem.constraints && problem.constraints.length > 0 && (
            <div>
              <h3 className="type-micro mb-3 text-bronze-dark/50">CONSTRAINTS</h3>
              <ul className="space-y-2 text-xs text-bronze-dark/80">
                {problem.constraints.map((c, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-orange shrink-0 mt-1.5" />
                    <code className="font-mono bg-surface-muted px-1.5 py-0.5 rounded text-charcoal border border-border-default/50 text-[11px]">
                      {c}
                    </code>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Sandbox Info */}
          <div className="p-3 rounded-xl bg-orange/5 border border-orange/15 text-[11px] text-bronze-dark/70 flex items-start gap-2">
            <Zap className="w-3.5 h-3.5 text-orange shrink-0 mt-0.5" />
            <span>
              Submissions execute in an isolated Python 3 subprocess with a 3.0s timeout.
            </span>
          </div>
        </div>

        {/* Right column: Code Editor & Results (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          {/* Editor Header Toolbar */}
          <div className="flex items-center justify-between text-xs px-1">
            <div className="flex items-center gap-2">
              <Code2 className="w-4 h-4 text-orange" />
              <span className="font-semibold text-charcoal">Python 3</span>
            </div>
            <button
              onClick={handleReset}
              disabled={running || submitting}
              className="flex items-center gap-1.5 text-bronze-dark/60 hover:text-charcoal transition-colors disabled:opacity-50"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset Code
            </button>
          </div>

          {/* Code Editor */}
          <CodeEditor
            value={code}
            onChange={handleCodeChange}
            onRun={handleRun}
            onSubmit={handleSubmit}
          />

          {/* Execution Controls */}
          <div className="flex items-center justify-between gap-3 pt-1">
            <div className="flex items-center gap-2">
              {/* Run Code Button */}
              <PBButton
                variant="secondary"
                size="sm"
                onClick={handleRun}
                disabled={running || submitting || !code.trim()}
                className="flex items-center gap-2"
              >
                {running ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5" />
                    Run Code
                  </>
                )}
              </PBButton>

              {/* Submit Button */}
              <PBButton
                variant="primary"
                size="sm"
                onClick={handleSubmit}
                disabled={running || submitting || !code.trim()}
                className="flex items-center gap-2"
              >
                {submitting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-white" />
                    Submitting...
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-3.5 h-3.5" />
                    Submit Solution
                  </>
                )}
              </PBButton>
            </div>

            <span className="text-[11px] text-bronze-dark/40 hidden sm:inline">
              Runs against {problem.test_count} test cases
            </span>
          </div>

          {/* API Error Box */}
          {apiError && (
            <div className="flex items-center gap-2 p-3 bg-danger-light border border-danger/20 rounded-xl text-xs text-danger">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              {apiError}
            </div>
          )}

          {/* Results Panel */}
          {result && <ResultsPanel result={result} mode={executionMode} />}
        </div>
      </div>
    </div>
  );
}

/* ───────────────────────────────────────────────────────────── */
/*  Main Export                                                  */
/* ───────────────────────────────────────────────────────────── */

export function CodingPractice() {
  const [problems, setProblems] = useState<CodingProblem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<CodingProblem | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [solvedIds, setSolvedIds] = useState<string[]>([]);

  useEffect(() => {
    setSolvedIds(getStoredSolvedIds());

    const load = async () => {
      try {
        const data = await listCodingProblems();
        setProblems(data);
      } catch (err) {
        setFetchError(err instanceof Error ? err.message : "Failed to load problems");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleProblemSolved = useCallback((id: string) => {
    saveSolvedId(id);
    setSolvedIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="w-6 h-6 text-orange animate-spin" />
        <span className="ml-3 text-sm text-bronze-dark/50">Loading coding challenges…</span>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="surface-card p-12 text-center rounded-2xl border border-border-default">
        <div className="w-12 h-12 rounded-xl bg-danger-light flex items-center justify-center mx-auto mb-4">
          <AlertTriangle className="w-5 h-5 text-danger" />
        </div>
        <h3 className="font-bold text-lg text-charcoal">Unable to load problems</h3>
        <p className="text-sm text-bronze-dark/50 mt-1">{fetchError}</p>
        <div className="mt-4">
          <PBButton
            variant="secondary"
            size="sm"
            onClick={() => window.location.reload()}
          >
            Retry
          </PBButton>
        </div>
      </div>
    );
  }

  if (selected) {
    return (
      <div className="animate-fade-in">
        <ProblemWorkspace
          problem={selected}
          isSolved={solvedIds.includes(selected.id)}
          onBack={() => setSelected(null)}
          onProblemSolved={handleProblemSolved}
        />
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <ProblemList
        problems={problems}
        solvedIds={solvedIds}
        onSelect={setSelected}
      />
    </div>
  );
}
