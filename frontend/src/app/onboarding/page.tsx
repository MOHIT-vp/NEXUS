"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  UploadCloud, CheckCircle2, ChevronRight, Code2,
  AlertCircle, FileText, X, Loader2, ArrowLeft,
} from "lucide-react";
import { PBButton } from "@/components/ui/pb-button";
import { PBInput } from "@/components/ui/pb-input";
import { Navbar } from "@/components/navigation/navbar";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { uploadResume } from "@/lib/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
type ValidationState = "idle" | "checking" | "valid" | "invalid";

const PROCESSING_STEPS = [
  { key: "upload", label: "Resume extracted" },
  { key: "skills", label: "Skills identified" },
  { key: "compare", label: "Comparing industry requirements" },
  { key: "roadmap", label: "Building learning roadmap" },
];

function GithubLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
    </svg>
  );
}

function GithubStatusIcon({ state }: { state: ValidationState }) {
  if (state === "checking") return <Loader2 className="w-4 h-4 text-bronze animate-spin-slow" />;
  if (state === "valid") return <CheckCircle2 className="w-4 h-4 text-success" />;
  if (state === "invalid") return <AlertCircle className="w-4 h-4 text-danger" />;
  return <GithubLogo className="w-4 h-4 text-charcoal" />;
}

export default function OnboardingPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [progress, setProgress] = useState("");
  const [processingStep, setProcessingStep] = useState(0);

  // Step 1
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [resumeError, setResumeError] = useState("");
  const [isDragging, setIsDragging] = useState(false);

  // Step 2
  const [leetcode, setLeetcode] = useState("");
  const [github, setGithub] = useState("");
  const [githubState, setGithubState] = useState<ValidationState>("idle");
  const [githubError, setGithubError] = useState("");
  const [githubUser, setGithubUser] = useState<{ login: string; avatar_url: string; public_repos: number } | null>(null);
  const [codingSolved, setCodingSolved] = useState("");
  const [cgpa, setCgpa] = useState("");
  const [consent, setConsent] = useState(false);

  const ALLOWED = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ];

  function validateFile(f: File) {
    if (!ALLOWED.includes(f.type)) return "Only PDF or DOCX files accepted.";
    if (f.size > 5 * 1024 * 1024) return "File must be under 5 MB.";
    return "";
  }

  function handleFileSelect(f: File) {
    const err = validateFile(f);
    if (err) { setResumeError(err); setResumeFile(null); return; }
    setResumeError("");
    setResumeFile(f);
  }

  const onDragOver = useCallback((e: React.DragEvent) => { e.preventDefault(); setIsDragging(true); }, []);
  const onDragLeave = useCallback(() => setIsDragging(false), []);
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setIsDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFileSelect(f);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleContinue() {
    if (!resumeFile) { setResumeError("You must upload a resume before continuing."); return; }
    setStep(2);
  }

  async function validateGitHub(username: string) {
    if (!username.trim()) { setGithubState("idle"); setGithubUser(null); return; }
    setGithubState("checking"); setGithubError(""); setGithubUser(null);
    try {
      const res = await fetch(`https://api.github.com/users/${encodeURIComponent(username.trim())}`);
      if (res.status === 404) { setGithubState("invalid"); setGithubError(`GitHub user "${username}" does not exist.`); return; }
      if (!res.ok) { setGithubState("invalid"); setGithubError("GitHub API error, try again."); return; }
      const d = await res.json();
      setGithubUser({ login: d.login, avatar_url: d.avatar_url, public_repos: d.public_repos });
      setGithubState("valid");
    } catch { setGithubState("invalid"); setGithubError("Network error checking GitHub."); }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError("");
    if (!resumeFile) { setSubmitError("Resume is required."); return; }
    if (github.trim() && githubState !== "valid") { setSubmitError("Verify GitHub username first."); return; }

    setIsSubmitting(true);
    setProcessingStep(0);
    setProgress("Initializing AI agents...");

    // Start artificial progress to keep user engaged during long backend process
    const uiTimer = setInterval(() => {
      setProcessingStep((prev) => {
        // Only advance automatically up to step 2 (Computing matches)
        if (prev < 2) return prev + 1;
        return prev;
      });
    }, 4500); // advance every 4.5 seconds

    try {
      const form = new FormData();
      form.append("file", resumeFile);
      if (leetcode.trim()) form.append("leetcode_handle", leetcode.trim());
      if (github.trim()) form.append("github_username", github.trim());
      if (codingSolved) form.append("coding_solved", codingSolved);
      if (cgpa) form.append("cgpa", cgpa);

      const data = await uploadResume(form);

      clearInterval(uiTimer);

      setProcessingStep(3);
      setProgress("Initializing your assessment tracker...");

      // Save the active run ID for convenience (Dashboard will check this)
      localStorage.setItem("active_run_id", data.run_id);
      
      // Redirect to the assessment status page
      router.push(`/assessment/${data.run_id}`);
    } catch (err: unknown) {
      clearInterval(uiTimer);
      const msg = err instanceof Error ? err.message : "Unexpected error.";
      setSubmitError(msg);
      setIsSubmitting(false);
      setProgress("");
      setProcessingStep(0);
    }
  }

  const canSubmit = consent && !!resumeFile && (githubState === "valid" || !github.trim()) && !isSubmitting;

  return (
    <div className="min-h-screen bg-ivory flex flex-col">
      {/* Top bar */}
      <header className="px-6 py-4 flex items-center justify-between max-w-3xl mx-auto w-full">
        <Link href="/" className="flex items-center gap-2 text-bronze-dark/60 hover:text-charcoal transition-colors">
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm font-medium">Back</span>
        </Link>
        <div className="flex items-center gap-2">
          <span className="text-2xl font-medium text-charcoal font-stardom">NEXUS</span>
        </div>
      </header>

      <main className="flex-1 flex items-start justify-center px-6 py-8">
        <div className="w-full max-w-2xl animate-slide-up">

          {/* ── Progress Indicator ── */}
          <div className="flex items-center justify-center mb-10 max-w-md mx-auto">
            {[
              { num: "01", label: "PROFILE", sub: "Resume + identity" },
              { num: "02", label: "SIGNALS", sub: "Coding + academics" },
            ].map((s, i) => (
              <div key={s.num} className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 transition-all duration-300 ${
                  step > i + 1 ? "bg-success text-white" :
                  step === i + 1 ? "bg-orange text-white" :
                  "bg-surface-muted text-bronze-dark/40 border border-border-default"
                }`}>
                  {step > i + 1 ? <CheckCircle2 className="w-4 h-4" /> : s.num}
                </div>
                <div className="hidden sm:block">
                  <p className={`text-xs font-semibold tracking-wide ${step >= i + 1 ? "text-charcoal" : "text-bronze-dark/40"}`}>
                    {s.label}
                  </p>
                  <p className="text-[11px] text-bronze-dark/40">{s.sub}</p>
                </div>
                {i === 0 && (
                  <div className={`w-16 h-px mx-4 transition-colors duration-300 ${step > 1 ? "bg-success" : "bg-border-default"}`} />
                )}
              </div>
            ))}
          </div>

          <div className="surface-card p-8 lg:p-10">

            {/* ── STEP 1: Resume ── */}
            {step === 1 && !isSubmitting && (
              <div className="space-y-6 animate-fade-in">
                <div>
                  <h2 className="type-h2 mb-2">Start with your resume.</h2>
                  <p className="type-body text-bronze-dark/60">
                    Upload the document you use to represent yourself professionally.
                  </p>
                </div>

                <input ref={fileInputRef} type="file" className="hidden"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={e => { const f = e.target.files?.[0]; if (f) handleFileSelect(f); }} />

                {!resumeFile ? (
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}
                    className={`border-2 border-dashed rounded-[16px] p-12 text-center flex flex-col items-center cursor-pointer transition-all group ${
                      isDragging ? "border-orange bg-orange/[0.03] scale-[1.01]"
                      : resumeError ? "border-danger/40 bg-danger-light/30"
                      : "border-border-strong hover:border-bronze hover:bg-surface-warm"
                    }`}
                  >
                    <div className="w-14 h-14 rounded-[14px] bg-surface-muted flex items-center justify-center mb-4 group-hover:scale-105 transition-transform">
                      <UploadCloud className={`w-6 h-6 ${resumeError ? "text-danger" : "text-bronze"}`} />
                    </div>
                    <h3 className="font-semibold text-charcoal mb-1">Drag & drop your resume</h3>
                    <p className="text-sm text-bronze-dark/50 mb-4">PDF or DOCX · max 5 MB</p>
                    <span className="text-sm font-medium text-bronze bg-surface-muted px-5 py-2 rounded-[10px] border border-border-default group-hover:bg-ivory-warm transition-colors">
                      Browse Files
                    </span>
                  </div>
                ) : (
                  <div className="border border-success/30 bg-success-light/30 rounded-[16px] p-5 flex items-center justify-between animate-scale-in">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-[12px] bg-success-light flex items-center justify-center">
                        <FileText className="w-5 h-5 text-success" />
                      </div>
                      <div>
                        <p className="font-semibold text-charcoal truncate max-w-xs">{resumeFile.name}</p>
                        <p className="text-xs text-bronze-dark/50">{(resumeFile.size / 1024).toFixed(1)} KB · Ready to upload</p>
                      </div>
                    </div>
                    <button
                      onClick={e => { e.stopPropagation(); setResumeFile(null); setResumeError(""); }}
                      className="w-8 h-8 rounded-full hover:bg-surface-muted flex items-center justify-center transition-colors"
                    >
                      <X className="w-4 h-4 text-bronze-dark/50" />
                    </button>
                  </div>
                )}

                {resumeError && (
                  <div className="flex items-center gap-2 text-danger text-sm font-medium">
                    <AlertCircle className="w-4 h-4 shrink-0" />{resumeError}
                  </div>
                )}

                <PBButton onClick={handleContinue} size="lg" className="w-full">
                  Continue <ChevronRight className="w-4 h-4" />
                </PBButton>
              </div>
            )}

            {/* ── STEP 2: Profile Signals ── */}
            {step === 2 && !isSubmitting && (
              <form onSubmit={handleSubmit} className="space-y-8 animate-fade-in">
                <div>
                  <h2 className="type-h2 mb-2">Your profile signals.</h2>
                  <p className="type-body text-bronze-dark/60">
                    Provide additional information for accurate company matching.
                  </p>
                </div>

                {/* Coding Profile */}
                <div className="space-y-4">
                  <p className="type-micro text-bronze">CODING PROFILE</p>

                  <PBInput
                    label="LeetCode Handle"
                    hint="(optional)"
                    placeholder="e.g. student123"
                    icon={<Code2 className="w-4 h-4" />}
                    value={leetcode}
                    onChange={e => setLeetcode(e.target.value)}
                  />

                  <div className="space-y-1.5 w-full">
                    <div className="relative flex rounded-[12px] w-full">
                      <div className="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none z-10">
                        <GithubStatusIcon state={githubState} />
                      </div>
                      <input
                        type="text"
                        placeholder="e.g. studentgithub"
                        className={`peer w-full bg-surface border rounded-[12px] py-3 pl-11 pr-4 text-[0.9375rem] text-charcoal placeholder-transparent focus:placeholder-bronze-dark/35 focus:outline-none focus:ring-2 transition-all duration-200 ${
                          githubState === "valid" ? "border-success focus:ring-success/15"
                          : githubState === "invalid" ? "border-danger focus:ring-danger/15"
                          : "border-border-default focus:border-bronze focus:ring-bronze/15"
                        }`}
                        value={github}
                        onChange={e => { setGithub(e.target.value); setGithubState("idle"); setGithubUser(null); }}
                        onBlur={() => { if (github.trim()) validateGitHub(github.trim()); }}
                      />
                      <label
                        className={cn(
                          "absolute top-1/2 translate-y-[-50%] bg-surface px-1 font-medium text-bronze-dark/80 pointer-events-none duration-150 transition-all",
                          "block whitespace-nowrap overflow-hidden text-ellipsis max-w-[calc(100%-1rem)]",
                          "peer-focus:top-0 peer-focus:left-3 peer-focus:text-xs peer-focus:text-bronze",
                          "peer-[:not(:placeholder-shown)]:top-0 peer-[:not(:placeholder-shown)]:left-3 peer-[:not(:placeholder-shown)]:text-xs",
                          "left-10"
                        )}
                      >
                        GitHub Username <span className="font-normal text-bronze-dark/60 ml-1.5">(optional)</span>
                      </label>
                    </div>
                    {githubState === "invalid" && (
                      <p className="text-sm text-danger font-medium flex items-center gap-1.5">
                        <AlertCircle className="w-3.5 h-3.5" />{githubError}
                      </p>
                    )}
                    {githubState === "valid" && githubUser && (
                      <div className="flex items-center gap-3 p-3 bg-success-light/50 border border-success/15 rounded-[12px] animate-scale-in">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={githubUser.avatar_url} alt={githubUser.login} className="w-8 h-8 rounded-full" />
                        <div>
                          <p className="text-sm font-semibold text-success">@{githubUser.login}</p>
                          <p className="text-xs text-success/70">{githubUser.public_repos} public repos · Verified ✓</p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Academic Signal */}
                <div className="space-y-4">
                  <p className="type-micro text-bronze">ACADEMIC SIGNAL</p>
                  <div className="grid grid-cols-2 gap-4">
                    <PBInput
                      label="Problems Solved"
                      hint="(LeetCode/HackerRank)"
                      type="number"
                      min={0}
                      max={5000}
                      placeholder="e.g. 150"
                      value={codingSolved}
                      onChange={e => setCodingSolved(e.target.value)}
                    />
                    <PBInput
                      label="CGPA"
                      hint="(optional)"
                      type="number"
                      step={0.01}
                      min={0}
                      max={10}
                      placeholder="e.g. 8.5"
                      value={cgpa}
                      onChange={e => setCgpa(e.target.value)}
                    />
                  </div>
                </div>

                {/* Consent */}
                <div className="flex items-start gap-3 p-4 bg-surface-warm rounded-[12px] border border-border-subtle">
                  <input
                    type="checkbox"
                    id="consent"
                    required
                    checked={consent}
                    onChange={e => setConsent(e.target.checked)}
                    className="w-4.5 h-4.5 mt-0.5 rounded border-border-strong text-charcoal focus:ring-charcoal/30 cursor-pointer accent-charcoal"
                  />
                  <div>
                    <label htmlFor="consent" className="text-sm font-semibold text-charcoal cursor-pointer">
                      I consent to data analysis
                    </label>
                    <p className="text-xs text-bronze-dark/50 mt-1 leading-relaxed">
                      I authorise the Placement Readiness Portal to analyse my resume and coding profiles. Data is processed locally and not stored in any database.
                    </p>
                  </div>
                </div>

                {submitError && (
                  <div className="flex items-center gap-2 text-danger text-sm p-3 bg-danger-light rounded-[10px] border border-danger/15 font-medium">
                    <AlertCircle className="w-4 h-4 shrink-0" />{submitError}
                  </div>
                )}

                <div className="flex gap-3">
                  <PBButton type="button" variant="secondary" size="lg" onClick={() => setStep(1)} className="w-1/3">
                    <ArrowLeft className="w-4 h-4" /> Back
                  </PBButton>
                  <PBButton type="submit" disabled={!canSubmit} size="lg" className="flex-1">
                    {isSubmitting
                      ? <><Loader2 className="w-4 h-4 animate-spin-slow" /> Analysing...</>
                      : <>Analyze my profile <ChevronRight className="w-4 h-4" /></>
                    }
                  </PBButton>
                </div>
              </form>
            )}

            {/* ── Processing State ── */}
            {isSubmitting && (
              <div className="space-y-8 animate-fade-in py-8">
                <div className="text-center">
                  <p className="type-micro text-orange mb-3">ANALYZING PROFILE</p>
                  <h2 className="type-h2">Processing your data...</h2>
                </div>

                <div className="space-y-3 max-w-sm mx-auto">
                  {PROCESSING_STEPS.map((ps, i) => {
                    const isComplete = i < processingStep;
                    const isCurrent = i === processingStep;
                    const isPending = i > processingStep;
                    return (
                      <div key={ps.key} className="flex items-center gap-3">
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 transition-all duration-300 ${
                          isComplete ? "bg-success" :
                          isCurrent ? "bg-orange" :
                          "bg-surface-muted border border-border-default"
                        }`}>
                          {isComplete ? (
                            <CheckCircle2 className="w-3.5 h-3.5 text-white" />
                          ) : isCurrent ? (
                            <Loader2 className="w-3.5 h-3.5 text-white animate-spin-slow" />
                          ) : (
                            <span className="w-1.5 h-1.5 rounded-full bg-border-strong" />
                          )}
                        </div>
                        <span className={`text-sm font-medium transition-colors ${
                          isComplete ? "text-success" :
                          isCurrent ? "text-charcoal" :
                          "text-bronze-dark/30"
                        }`}>
                          {isComplete ? "✓ " : isCurrent ? "→ " : ""}{ps.label}
                        </span>
                      </div>
                    );
                  })}
                </div>

                <p className="text-center text-xs text-bronze-dark/40">
                  This may take a moment while our agents process your profile.
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
