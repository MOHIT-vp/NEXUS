"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { Loader } from "@/components/ui/loader";
import {
  Clock,
  CheckCircle2,
  XCircle,
  ArrowRight,
  ExternalLink,
  Loader2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { PBButton } from "@/components/ui/pb-button";
import { getWorkflowStatus, ResumePerfectionEvaluation } from "@/lib/api";
import { ResumePerfectionCard } from "@/components/resume/resume-perfection-card";
import Link from "next/link";

export default function AssessmentStatusPage() {
  const router = useRouter();
  const params = useParams();
  const runId = params.run_id as string;

  const [status, setStatus] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [perfectionEvaluation, setPerfectionEvaluation] = useState<ResumePerfectionEvaluation | null>(null);

  useEffect(() => {
    if (!runId) return;

    let intervalId: NodeJS.Timeout;

    const checkStatus = async () => {
      try {
        const response = await getWorkflowStatus(runId);

        setStatus(response.status);
        setCurrentStep(response.current_step || null);

        // Stop polling on terminal states
        if (
          response.status === "published" ||
          response.status === "approved" ||
          response.status === "rejected"
        ) {
          if (intervalId) clearInterval(intervalId);
        }
      } catch (err) {
        console.error("Error fetching assessment status:", err);
        setError("Failed to fetch assessment status.");
        if (intervalId) clearInterval(intervalId);
      }
    };

    // Initial check
    checkStatus();

    // Poll every 3 seconds if not in a terminal state
    intervalId = setInterval(() => {
      if (status !== "published" && status !== "rejected" && status !== "approved") {
        checkStatus();
      } else {
        clearInterval(intervalId);
      }
    }, 3000);

    return () => clearInterval(intervalId);
  }, [runId, status]);

  if (error) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-ivory gap-4 p-8 text-center">
        <div className="w-16 h-16 rounded-full bg-danger-light/20 flex items-center justify-center">
          <XCircle className="w-8 h-8 text-danger" />
        </div>
        <h2 className="type-h3 text-charcoal">Error Checking Status</h2>
        <p className="text-sm text-bronze-dark/50">{error}</p>
        <PBButton onClick={() => router.push("/onboarding")} variant="secondary" className="mt-4">
          Return to Onboarding
        </PBButton>
      </div>
    );
  }

  if (!status || status === "running" || status === "init") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-ivory">
        <div className="flex flex-col items-center gap-6 mt-10 max-w-sm text-center">
          <Loader />
          <h2 className="type-h3 text-charcoal">Analyzing Profile</h2>
          <p className="text-sm text-bronze-dark/60">
            Your assessment is being prepared by our AI agents. This may take a moment.
            <br />
            <br />
            <span className="font-medium text-bronze">Current Step:</span>{" "}
            <span className="font-semibold text-charcoal capitalize">
              {(currentStep || "Initializing").replace(/_/g, " ")}
            </span>
          </p>
        </div>
      </div>
    );
  }

  if (status === "rejected") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-ivory p-6">
        <div className="flex flex-col items-center gap-6 mt-10 max-w-sm text-center">
          <div className="w-20 h-20 rounded-[20px] bg-danger-light/20 flex items-center justify-center">
            <XCircle className="w-10 h-10 text-danger" />
          </div>
          <h2 className="type-h2 text-charcoal">Assessment Rejected</h2>
          <p className="text-sm text-bronze-dark/60">
            Your readiness assessment was reviewed and rejected by the Placement Officer.
            Please contact the placement cell for more details.
          </p>
          <PBButton onClick={() => router.push("/onboarding")} variant="primary" className="mt-4">
            Start New Assessment
          </PBButton>
        </div>
      </div>
    );
  }

  const isApproved = status === "approved" || status === "published";

  return (
    <div className="min-h-screen bg-ivory py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Navigation Bar / Breadcrumb */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border-subtle pb-5">
          <div>
            <Link href="/" className="text-xl font-bold font-stardom text-charcoal tracking-tight">
              NEXUS
            </Link>
            <p className="text-xs text-bronze-dark/60 mt-0.5">
              Placement Readiness & Resume Perfection Evaluation
            </p>
          </div>

          <div className="flex items-center gap-3">
            {isApproved ? (
              <PBButton
                onClick={() => router.push("/dashboard")}
                variant="primary"
                className="bg-success hover:bg-success/90 text-white"
              >
                Go to Placement Dashboard <ArrowRight className="w-4 h-4 ml-1.5" />
              </PBButton>
            ) : (
              <PBButton
                onClick={() => window.location.reload()}
                variant="secondary"
                size="sm"
              >
                Refresh Approval Status
              </PBButton>
            )}
          </div>
        </div>

        {/* Approval Banner if Approved */}
        {isApproved && (
          <div className="p-5 rounded-2xl bg-success-light/40 border border-success/30 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-success text-white flex items-center justify-center shrink-0">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-charcoal">Assessment Approved & Published!</h3>
                <p className="text-xs text-bronze-dark/80">
                  The Placement Cell has approved your readiness plan. Your full dashboard is now unlocked.
                </p>
              </div>
            </div>
            <PBButton onClick={() => router.push("/dashboard")} variant="primary" size="sm">
              Open Dashboard <ArrowRight className="w-4 h-4 ml-1.5" />
            </PBButton>
          </div>
        )}

        {/* Main Content Grid: Status Sidebar + Resume Perfection Evaluation */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
          {/* Status Column */}
          <div className="space-y-6">
            <div className="surface-card p-6 space-y-5">
              <div className="flex items-center gap-3">
                <div
                  className={`w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 ${
                    isApproved ? "bg-success-light text-success" : "bg-warning-light text-warning"
                  }`}
                >
                  {isApproved ? (
                    <CheckCircle2 className="w-6 h-6" />
                  ) : (
                    <Clock className="w-6 h-6" />
                  )}
                </div>
                <div>
                  <h3 className="type-h3 text-charcoal">
                    {isApproved ? "Approved & Ready" : "Awaiting Officer Review"}
                  </h3>
                  <p className="text-xs text-bronze-dark/50">Run ID: {runId.slice(0, 8)}...</p>
                </div>
              </div>

              {/* Status Checklist */}
              <div className="p-4 rounded-xl bg-surface-warm/50 border border-border-subtle space-y-3">
                <p className="text-xs font-semibold text-charcoal uppercase tracking-wider">
                  Workflow Milestones
                </p>
                <ul className="space-y-2.5 text-xs">
                  <li className="flex items-center gap-2.5 font-medium text-charcoal">
                    <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                    <span>Resume extracted & parsed</span>
                  </li>
                  <li className="flex items-center gap-2.5 font-medium text-charcoal">
                    <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                    <span>Skills & gap analysis complete</span>
                  </li>
                  <li className="flex items-center gap-2.5 font-medium text-charcoal">
                    <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                    <span>Job match scoring computed</span>
                  </li>
                  <li className="flex items-center gap-2.5 font-medium text-charcoal">
                    {perfectionEvaluation ? (
                      <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                    ) : (
                      <ShieldCheck className="w-4 h-4 text-orange shrink-0" />
                    )}
                    <span>
                      {perfectionEvaluation
                        ? `Resume perfection verified (${perfectionEvaluation.overall_score}% · ${perfectionEvaluation.tier_label})`
                        : "Resume perfection check (in progress)"}
                    </span>
                  </li>
                  <li
                    className={`flex items-center gap-2.5 font-medium ${
                      isApproved ? "text-charcoal" : "text-warning"
                    }`}
                  >
                    {isApproved ? (
                      <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                    ) : (
                      <Loader2 className="w-4 h-4 text-warning animate-spin shrink-0" />
                    )}
                    <span>
                      {isApproved
                        ? "Placement Cell review approved"
                        : "Placement Cell review pending"}
                    </span>
                  </li>
                </ul>
              </div>

              <div className="space-y-3 pt-1">
                <p className="text-xs text-bronze-dark/60 leading-relaxed">
                  While your profile awaits Placement Cell sign-off, take the Resume Perfection check on the right to verify how thoroughly you know your own resume claims.
                </p>

                <div className="pt-2">
                  <Link
                    href="/officer"
                    target="_blank"
                    className="text-xs text-bronze-dark/50 hover:text-primary transition-colors flex items-center gap-1.5"
                  >
                    Demo: Open Placement Officer Console <ExternalLink className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            </div>

            {/* Why This Matters Box */}
            <div className="p-5 rounded-2xl bg-surface border border-border-subtle space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-charcoal flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-orange" /> Why Resume Perfection?
              </h4>
              <p className="text-xs text-bronze-dark/70 leading-relaxed">
                Campus placement interviewers frequently reject candidates who cannot defend technical decisions or explain the internal mechanics of projects listed on their resume.
              </p>
            </div>
          </div>

          {/* Resume Perfection Interactive Area */}
          <div className="lg:col-span-2">
            <ResumePerfectionCard
              runId={runId}
              onEvaluationComplete={(evalResult) => setPerfectionEvaluation(evalResult)}
              title="Resume Perfection & Knowledge Verification"
              subtitle="Our AI analyzed your uploaded resume. Answer these targeted questions to evaluate how authentically and deeply you know your listed projects, technologies, and metrics."
            />
          </div>
        </div>
      </div>
    </div>
  );
}
