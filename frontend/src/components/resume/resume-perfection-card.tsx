"use client";

import { useEffect, useState } from "react";
import {
  ShieldCheck,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Sparkles,
  AlertTriangle,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  Award,
  Layers,
  Code2,
  Bug,
  LineChart,
  Loader2,
  BookOpen,
} from "lucide-react";
import { PBButton } from "@/components/ui/pb-button";
import { PBBadge } from "@/components/ui/pb-badge";
import { ScoreGauge } from "@/components/ui/score-gauge";
import {
  ResumePerfectionQuestion,
  ResumePerfectionEvaluation,
  StudentAnswerItem,
  getResumePerfection,
  submitResumePerfection,
  regenerateResumePerfection,
} from "@/lib/api";

interface ResumePerfectionCardProps {
  runId: string;
  initialEvaluation?: ResumePerfectionEvaluation | null;
  initialQuestions?: ResumePerfectionQuestion[];
  onEvaluationComplete?: (evaluation: ResumePerfectionEvaluation) => void;
  title?: string;
  subtitle?: string;
}

export function ResumePerfectionCard({
  runId,
  initialEvaluation = null,
  initialQuestions,
  onEvaluationComplete,
  title = "Resume Perfection & Knowledge Verification",
  subtitle = "Evaluate your mastery of your listed projects, skills, and technical claims before facing campus placement interviewers.",
}: ResumePerfectionCardProps) {
  const [questions, setQuestions] = useState<ResumePerfectionQuestion[]>(initialQuestions || []);
  const [evaluation, setEvaluation] = useState<ResumePerfectionEvaluation | null>(initialEvaluation);
  const [loading, setLoading] = useState(!initialQuestions && !initialEvaluation);
  const [submitting, setSubmitting] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, number>>({});
  const [studentNotes, setStudentNotes] = useState<Record<string, string>>({});
  const [expandedQuestion, setExpandedQuestion] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load questions or existing evaluation if not supplied
  useEffect(() => {
    if (!runId) return;
    if (initialEvaluation) {
      setEvaluation(initialEvaluation);
      return;
    }
    if (initialQuestions && initialQuestions.length > 0) {
      setQuestions(initialQuestions);
      setLoading(false);
      return;
    }

    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await getResumePerfection(runId);
        if (res.evaluation) {
          setEvaluation(res.evaluation);
        }
        if (res.questions && res.questions.length > 0) {
          setQuestions(res.questions);
        }
      } catch (err) {
        console.error("Failed to load resume perfection questions:", err);
        setError("Unable to load resume verification questions. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [runId, initialEvaluation, initialQuestions]);

  const handleSelectOption = (questionId: string, optionIdx: number) => {
    setSelectedAnswers((prev) => ({
      ...prev,
      [questionId]: optionIdx,
    }));
  };

  const handleNoteChange = (questionId: string, text: string) => {
    setStudentNotes((prev) => ({
      ...prev,
      [questionId]: text,
    }));
  };

  const handleSubmit = async () => {
    if (!runId) return;

    const answeredCount = Object.keys(selectedAnswers).length;
    if (answeredCount === 0) {
      setError("Please answer at least one question before submitting.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const answers: StudentAnswerItem[] = questions.map((q) => ({
        question_id: q.id,
        selected_option_index:
          selectedAnswers[q.id] !== undefined ? selectedAnswers[q.id] : -1,
        student_notes: studentNotes[q.id] || undefined,
      }));

      const res = await submitResumePerfection(runId, answers);
      setEvaluation(res.evaluation);
      if (onEvaluationComplete) {
        onEvaluationComplete(res.evaluation);
      }
    } catch (err) {
      console.error("Submission failed:", err);
      setError("Failed to evaluate answers. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetake = async () => {
    if (!runId) return;
    setRegenerating(true);
    setError(null);
    try {
      const res = await regenerateResumePerfection(runId);
      setQuestions(res.questions || []);
      setEvaluation(null);
      setSelectedAnswers({});
      setStudentNotes({});
    } catch (err) {
      console.error("Failed to regenerate questions:", err);
      setError("Could not regenerate questions. Please try again.");
    } finally {
      setRegenerating(false);
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case "project_architecture":
        return <Layers className="w-4 h-4 text-orange" />;
      case "tech_depth":
        return <Code2 className="w-4 h-4 text-primary" />;
      case "practical_debugging":
        return <Bug className="w-4 h-4 text-warning" />;
      case "metrics_validation":
      case "tradeoffs":
      default:
        return <LineChart className="w-4 h-4 text-bronze" />;
    }
  };

  if (loading) {
    return (
      <div className="surface-card p-8 flex flex-col items-center justify-center text-center gap-4">
        <Loader2 className="w-8 h-8 text-orange animate-spin" />
        <p className="text-sm font-medium text-charcoal">
          Analyzing resume claims & generating verification questions...
        </p>
      </div>
    );
  }

  // -------------------------------------------------------------------------
  // VIEW: EVALUATION COMPLETED
  // -------------------------------------------------------------------------
  if (evaluation) {
    const answeredTotal = evaluation.total_questions;
    const answeredCorrect = evaluation.correct_count;
    const scorePct = evaluation.overall_score;

    return (
      <div className="surface-card p-6 lg:p-8 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border-subtle pb-6">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-orange/10 text-orange">
                <ShieldCheck className="w-5 h-5" />
              </span>
              <h3 className="type-h3 text-charcoal">Resume Perfection Scorecard</h3>
            </div>
            <p className="text-xs text-bronze-dark/60">
              Evaluated based on your verified claims, architecture decisions, and technical depth.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <PBButton
              variant="secondary"
              size="sm"
              onClick={handleRetake}
              disabled={regenerating}
            >
              {regenerating ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Generating...
                </>
              ) : (
                <>
                  <RotateCcw className="w-3.5 h-3.5 mr-1.5" /> Retake Verification
                </>
              )}
            </PBButton>
          </div>
        </div>

        {/* Score & Tier Banner */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center bg-surface-warm/40 p-6 rounded-2xl border border-border-subtle">
          <div className="flex flex-col items-center justify-center text-center md:border-r md:border-border-subtle pr-0 md:pr-6">
            <ScoreGauge
              score={scorePct}
              maxScore={100}
              size={140}
              strokeWidth={8}
              label="Perfection Score"
            />
            <div className="mt-2 text-center">
              <span
                className="inline-block px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider text-white"
                style={{ backgroundColor: evaluation.tier_color || "#2D8A4E" }}
              >
                {evaluation.tier_label}
              </span>
              <p className="text-xs text-bronze-dark/60 mt-1">
                {answeredCorrect} of {answeredTotal} claims verified
              </p>
            </div>
          </div>

          <div className="md:col-span-2 space-y-4">
            <div>
              <h4 className="text-sm font-semibold text-charcoal mb-1 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-orange" /> Evaluator Verdict
              </h4>
              <p className="text-sm text-bronze-dark/80 leading-relaxed">
                {evaluation.summary}
              </p>
            </div>

            {/* Category Breakdown Bars */}
            <div className="space-y-2 pt-2">
              <p className="text-xs font-semibold text-charcoal uppercase tracking-wider">
                Claim Alignment Breakdown
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {evaluation.category_breakdown.map((cat) => (
                  <div
                    key={cat.category}
                    className="p-3 bg-surface rounded-xl border border-border-subtle"
                  >
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <span className="font-medium text-charcoal truncate">
                        {cat.category_label}
                      </span>
                      <span
                        className="font-bold"
                        style={{
                          color:
                            cat.score_percentage >= 80
                              ? "#2D8A4E"
                              : cat.score_percentage >= 50
                              ? "#D97706"
                              : "#DC2626",
                        }}
                      >
                        {cat.score_percentage}%
                      </span>
                    </div>
                    <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{
                          width: `${cat.score_percentage}%`,
                          backgroundColor:
                            cat.score_percentage >= 80
                              ? "#2D8A4E"
                              : cat.score_percentage >= 50
                              ? "#D97706"
                              : "#DC2626",
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Actionable Recommendations for Technical Interviews */}
        {evaluation.recommendations && evaluation.recommendations.length > 0 && (
          <div className="p-4 bg-orange/5 border border-orange/20 rounded-2xl space-y-2">
            <h4 className="text-xs font-bold uppercase tracking-wider text-orange flex items-center gap-1.5">
              <BookOpen className="w-4 h-4" /> Placement Interview Defense Strategy
            </h4>
            <ul className="space-y-1.5 text-xs text-charcoal">
              {evaluation.recommendations.map((rec, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-orange mt-1.5 shrink-0" />
                  <span>{rec}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Question-by-Question Deep Dive */}
        <div className="space-y-3 pt-2">
          <h4 className="text-sm font-semibold text-charcoal">
            Detailed Claim Verification Review
          </h4>
          <p className="text-xs text-bronze-dark/50">
            Click on each question to review your answer, the authoritative engineering rationale, and follow-up questions interviewer will ask.
          </p>

          <div className="divide-y divide-border-subtle border border-border-subtle rounded-2xl overflow-hidden bg-surface">
            {evaluation.question_results.map((res, i) => {
              const isExpanded = expandedQuestion === res.question_id;
              return (
                <div key={res.question_id} className="p-4 transition-colors hover:bg-surface-warm/30">
                  <div
                    className="flex items-start justify-between gap-4 cursor-pointer"
                    onClick={() =>
                      setExpandedQuestion(isExpanded ? null : res.question_id)
                    }
                  >
                    <div className="flex items-start gap-3 min-w-0">
                      <div className="mt-0.5 shrink-0">
                        {res.is_correct ? (
                          <CheckCircle2 className="w-5 h-5 text-success" />
                        ) : (
                          <XCircle className="w-5 h-5 text-danger" />
                        )}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className="text-xs font-bold text-orange uppercase tracking-wider">
                            Q{i + 1} · {res.category_label}
                          </span>
                          <span className="text-[11px] px-2 py-0.5 rounded-md bg-surface-muted text-bronze-dark/70 font-medium">
                            {res.target_claim}
                          </span>
                        </div>
                        <p className="text-sm font-medium text-charcoal line-clamp-2">
                          {res.question}
                        </p>
                      </div>
                    </div>

                    <div className="shrink-0 flex items-center gap-2">
                      <span
                        className={`text-xs font-bold px-2 py-1 rounded-md ${
                          res.is_correct
                            ? "bg-success-light text-success"
                            : "bg-danger-light text-danger"
                        }`}
                      >
                        {res.is_correct ? "Verified" : "Discrepancy"}
                      </span>
                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4 text-bronze-dark/40" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-bronze-dark/40" />
                      )}
                    </div>
                  </div>

                  {/* Expanded Content */}
                  {isExpanded && (
                    <div className="mt-4 pt-4 border-t border-border-subtle space-y-3 text-xs pl-8">
                      <div>
                        <span className="font-semibold text-bronze-dark/60 block mb-1">
                          Your Answer:
                        </span>
                        <p
                          className={`p-2.5 rounded-lg border ${
                            res.is_correct
                              ? "bg-success-light/40 border-success/30 text-charcoal"
                              : "bg-danger-light/30 border-danger/30 text-charcoal"
                          }`}
                        >
                          {res.selected_text}
                        </p>
                      </div>

                      {!res.is_correct && (
                        <div>
                          <span className="font-semibold text-success block mb-1">
                            Authentic Engineering Answer:
                          </span>
                          <p className="p-2.5 rounded-lg bg-success-light/30 border border-success/30 text-charcoal font-medium">
                            {res.correct_text}
                          </p>
                        </div>
                      )}

                      <div className="p-3 rounded-lg bg-surface-warm border border-border-subtle space-y-1">
                        <span className="font-semibold text-charcoal block">
                          Why Interviewers Test This:
                        </span>
                        <p className="text-bronze-dark/80 leading-relaxed">
                          {res.explanation}
                        </p>
                      </div>

                      {res.interview_tip && (
                        <div className="p-3 rounded-lg bg-orange/5 border border-orange/15 text-orange-dark">
                          <span className="font-semibold block mb-0.5 text-orange">
                            Placement Interviewer Follow-up:
                          </span>
                          <p className="text-charcoal/90">{res.interview_tip}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  // -------------------------------------------------------------------------
  // VIEW: QUESTIONNAIRE MODE (Take Test)
  // -------------------------------------------------------------------------
  const totalQuestions = questions.length;
  const answeredCount = Object.keys(selectedAnswers).length;
  const progressPct =
    totalQuestions > 0 ? Math.round((answeredCount / totalQuestions) * 100) : 0;

  return (
    <div className="surface-card p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div className="border-b border-border-subtle pb-4">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="p-1.5 rounded-lg bg-orange/10 text-orange">
            <ShieldCheck className="w-5 h-5" />
          </span>
          <h3 className="type-h3 text-charcoal">{title}</h3>
        </div>
        <p className="text-xs text-bronze-dark/70 leading-relaxed">
          {subtitle}
        </p>

        {/* Progress Bar */}
        <div className="mt-4 pt-3 border-t border-border-subtle flex items-center justify-between text-xs">
          <span className="text-bronze-dark/60 font-medium">
            Answered: {answeredCount} of {totalQuestions} claims
          </span>
          <span className="text-orange font-semibold">{progressPct}% Complete</span>
        </div>
        <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden mt-1.5">
          <div
            className="h-full rounded-full bg-orange transition-all duration-300"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-danger-light/30 border border-danger/30 text-danger text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Questions List */}
      <div className="space-y-6">
        {questions.map((q, qIndex) => {
          const selectedOption = selectedAnswers[q.id];
          return (
            <div
              key={q.id}
              className="p-5 rounded-2xl bg-surface border border-border-subtle hover:border-orange/30 transition-all space-y-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-bold text-orange uppercase tracking-wider flex items-center gap-1.5">
                      {getCategoryIcon(q.category)}
                      Claim {qIndex + 1} · {q.category_label}
                    </span>
                    <span className="text-[11px] px-2 py-0.5 rounded-md bg-surface-muted text-charcoal font-medium border border-border-subtle">
                      {q.target_claim}
                    </span>
                  </div>
                  <h4 className="text-sm font-semibold text-charcoal leading-snug pt-1">
                    {q.question}
                  </h4>
                  {q.context && (
                    <p className="text-xs text-bronze-dark/50 italic">
                      Context: {q.context}
                    </p>
                  )}
                </div>

                <PBBadge variant={q.difficulty === "hard" ? "high" : "medium"}>
                  {q.difficulty}
                </PBBadge>
              </div>

              {/* 4 Options */}
              <div className="space-y-2 pt-1">
                {q.options.map((opt, optIdx) => {
                  const isChecked = selectedOption === optIdx;
                  return (
                    <label
                      key={optIdx}
                      onClick={() => handleSelectOption(q.id, optIdx)}
                      className={`flex items-start gap-3 p-3.5 rounded-xl border text-xs cursor-pointer transition-all ${
                        isChecked
                          ? "bg-orange/8 border-orange text-charcoal font-medium shadow-sm"
                          : "bg-surface hover:bg-surface-warm border-border-subtle text-charcoal/80"
                      }`}
                    >
                      <input
                        type="radio"
                        name={`question_${q.id}`}
                        checked={isChecked}
                        onChange={() => handleSelectOption(q.id, optIdx)}
                        className="mt-0.5 text-orange focus:ring-orange accent-orange shrink-0 cursor-pointer"
                      />
                      <span className="leading-relaxed">{opt}</span>
                    </label>
                  );
                })}
              </div>

              {/* Optional brief notes */}
              <div className="pt-1">
                <input
                  type="text"
                  placeholder="Optional: Brief personal note or implementation detail for this claim..."
                  value={studentNotes[q.id] || ""}
                  onChange={(e) => handleNoteChange(q.id, e.target.value)}
                  className="w-full text-xs px-3 py-2 rounded-lg bg-surface-warm border border-border-subtle focus:outline-none focus:border-orange text-charcoal placeholder:text-bronze-dark/40"
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Submission CTA */}
      <div className="pt-4 border-t border-border-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <p className="text-xs text-bronze-dark/50">
          Your answers are evaluated to score your resume depth and prepare you for technical placement rounds.
        </p>

        <PBButton
          onClick={handleSubmit}
          disabled={submitting || answeredCount === 0}
          className="w-full sm:w-auto px-6"
        >
          {submitting ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Evaluating Perfection...
            </>
          ) : (
            <>
              <ShieldCheck className="w-4 h-4 mr-2" />
              Evaluate Resume Perfection ({answeredCount}/{totalQuestions})
            </>
          )}
        </PBButton>
      </div>
    </div>
  );
}
