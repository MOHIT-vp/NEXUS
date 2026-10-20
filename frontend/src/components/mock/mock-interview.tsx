"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle, ArrowLeft, BookOpenCheck, Brain, CheckCircle2, ChevronLeft, ChevronRight, Clock, Code2, Cpu,
  Loader2, Mic, MicOff, PenLine, RotateCcw, XCircle,
} from "lucide-react";
import { PBButton } from "@/components/ui/pb-button";
import {
  getMockHistory, getMockSections, startMock, submitMock,
  type MockHistoryItem, type MockResult, type MockSection, type MockSession,
} from "@/lib/api";

const ICONS: Record<string, typeof Brain> = {
  aptitude: Brain, verbal: BookOpenCheck, cs_fundamentals: Cpu, coding: Code2, spoken_english: Mic, essay: PenLine,
};

type Stage = "home" | "setup" | "test" | "result";

const fmt = (sec: number) => `${Math.floor(sec / 60)}:${String(Math.max(0, sec % 60)).padStart(2, "0")}`;
const wordCount = (t: string) => (t.trim() ? t.trim().split(/\s+/).length : 0);

/* ------------------------------------------------------------------ */
/* Speech-to-text for the spoken English round (Chrome / Edge)        */
/* ------------------------------------------------------------------ */
/* eslint-disable @typescript-eslint/no-explicit-any */
function getRecognition(): any {
  if (typeof window === "undefined") return null;
  const R = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  if (!R) return null;
  const r = new R();
  r.continuous = true;
  r.interimResults = true;
  r.lang = (typeof navigator !== "undefined" && navigator.language) ? navigator.language : "en-IN";
  return r;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

export function MockInterview() {
  const [stage, setStage] = useState<Stage>("home");
  const [sections, setSections] = useState<MockSection[]>([]);
  const [history, setHistory] = useState<MockHistoryItem[]>([]);
  const [chosen, setChosen] = useState<MockSection | null>(null);
  const [count, setCount] = useState(10);
  const [minutes, setMinutes] = useState(15);
  const [subjects, setSubjects] = useState<string[]>([]);
  const [session, setSession] = useState<MockSession | null>(null);
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [durations, setDurations] = useState<Record<string, number>>({});
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [result, setResult] = useState<MockResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [recording, setRecording] = useState(false);
  const recRef = useRef<{ stop: () => void } | null>(null);
  const recStart = useRef(0);
  const submitted = useRef(false);

  const loadHome = useCallback(() => {
    getMockSections().then(setSections).catch((e) => setError(e instanceof Error ? e.message : "Could not load sections."));
    getMockHistory().then(setHistory).catch(() => setHistory([]));
  }, []);

  useEffect(() => { loadHome(); }, [loadHome]);

  function openSetup(s: MockSection) {
    setChosen(s);
    setCount(Math.min(s.default_count, s.available));
    setMinutes(s.default_minutes);
    setSubjects(s.subjects ?? []);
    setError("");
    setStage("setup");
  }

  async function begin() {
    if (!chosen) return;
    setBusy(true);
    setError("");
    try {
      const max = chosen.subject_counts ? subjects.reduce((n, sub) => n + (chosen.subject_counts?.[sub] ?? 0), 0) : chosen.available;
      const s = await startMock({ section: chosen.id, count: Math.min(count, Math.max(1, max)), minutes, subjects: chosen.subjects ? subjects : undefined });
      const initial: Record<string, unknown> = {};
      if (s.kind === "coding") s.questions.forEach((q) => { initial[q.id] = q.starter_code ?? ""; });
      submitted.current = false;
      setAnswers(initial);
      setDurations({});
      setCurrent(0);
      setSession(s);
      setSecondsLeft(s.minutes * 60);
      setStage("test");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the test.");
    } finally {
      setBusy(false);
    }
  }

  const stopRecording = useCallback(() => {
    if (recRef.current) {
      try {
        recRef.current.stop();
      } catch (e) {
        console.warn("Error stopping speech recognition:", e);
      }
      recRef.current = null;
    }
    setRecording(false);
  }, []);

  const finish = useCallback(async () => {
    if (!session || submitted.current) return;
    submitted.current = true;
    stopRecording();
    setBusy(true);
    try {
      const r = await submitMock({ session_token: session.session_token, answers, durations });
      setResult(r);
      setStage("result");
      getMockHistory().then(setHistory).catch(() => {});
    } catch (e) {
      submitted.current = false;
      setError(e instanceof Error ? e.message : "Could not submit.");
    } finally {
      setBusy(false);
    }
  }, [session, answers, durations, stopRecording]);

  // Countdown; submits automatically when time runs out
  useEffect(() => {
    if (stage !== "test") return;
    const t = setInterval(() => setSecondsLeft((s) => s - 1), 1000);
    return () => clearInterval(t);
  }, [stage]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (stage === "test" && secondsLeft <= 0) finish();
  }, [stage, secondsLeft, finish]);

  async function startRecording(qid: string) {
    setError("");

    // 1. Verify browser support
    const R = typeof window !== "undefined" && ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
    if (!R) {
      setError("Speech recognition is not supported in this browser. Please open in Google Chrome or Microsoft Edge, or type your answer directly in the text box.");
      return;
    }

    // 2. Request mic permission explicitly to trigger permission prompt and catch errors
    try {
      if (typeof navigator !== "undefined" && navigator.mediaDevices?.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach((track) => track.stop());
      }
    } catch (err: any) {
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        setError("Microphone permission was blocked. Please click the lock icon in your browser address bar to allow microphone access, or type your answer.");
        return;
      }
      if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        setError("No microphone found on your device. Please plug in a microphone, or type your answer.");
        return;
      }
    }

    const r = getRecognition();
    if (!r) return;

    const before = String(answers[qid] ?? "").trim();

    /* eslint-disable @typescript-eslint/no-explicit-any */
    r.onresult = (ev: any) => {
      let text = "";
      for (let i = 0; i < ev.results.length; i++) {
        text += ev.results[i][0].transcript + " ";
      }
      const newText = text.trim();
      setAnswers((a) => ({
        ...a,
        [qid]: before ? `${before} ${newText}` : newText,
      }));
    };

    r.onerror = (ev: any) => {
      console.warn("Speech recognition error:", ev.error);
      setRecording(false);
      if (ev.error === "not-allowed") {
        setError("Microphone permission was denied by the browser. Please allow microphone access in your browser settings, or type your answer.");
      } else if (ev.error === "no-speech") {
        setError("No speech was detected. Please speak closer to your microphone, or type your answer.");
      } else if (ev.error === "network") {
        setError("Speech recognition network error. Chrome's speech recognizer requires an internet connection to Google's speech servers. You can type your answer instead.");
      } else if (ev.error === "audio-capture") {
        setError("No microphone detected. Please check your audio input settings, or type your answer.");
      } else {
        setError(`Speech recognition note: ${ev.error}. You can continue by typing your answer.`);
      }
    };

    r.onend = () => {
      setDurations((d) => ({ ...d, [qid]: (d[qid] ?? 0) + (Date.now() - recStart.current) / 1000 }));
      setRecording(false);
    };
    /* eslint-enable @typescript-eslint/no-explicit-any */

    try {
      recStart.current = Date.now();
      r.start();
      recRef.current = r;
      setRecording(true);
    } catch (err: any) {
      console.warn("Failed to start speech recognition:", err);
      setError("Could not start speech recognition. You can type your answer directly in the box below.");
      setRecording(false);
    }
  }

  /* ------------------------------ HOME ------------------------------ */
  if (stage === "home") {
    return (
      <div className="space-y-6 animate-fade-in">
        <div>
          <h2 className="type-h2 mb-1">Mock interview</h2>
          <p className="type-body text-bronze-dark/60">Practise each placement round on its own — choose how many questions and set your own timer.</p>
        </div>
        {error && <p className="text-sm text-danger flex items-center gap-2"><AlertCircle className="w-4 h-4" />{error}</p>}
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {sections.map((s) => {
            const Icon = ICONS[s.id] ?? Brain;
            return (
              <button key={s.id} onClick={() => openSetup(s)}
                className="surface-card p-5 text-left group hover:-translate-y-0.5 hover:shadow-lg hover:border-orange/40 transition-all">
                <div className="w-11 h-11 rounded-[12px] bg-ivory-warm border border-bronze/15 flex items-center justify-center mb-4 group-hover:bg-orange group-hover:border-orange transition-colors">
                  <Icon className="w-5 h-5 text-bronze-dark group-hover:text-white transition-colors" />
                </div>
                <h3 className="font-semibold text-charcoal mb-1">{s.title}</h3>
                <p className="text-sm text-bronze-dark/60 mb-3">{s.description}</p>
                <p className="text-xs font-semibold text-orange">{s.available} questions available · default {s.default_minutes} min</p>
              </button>
            );
          })}
        </div>

        <div className="surface-card p-6">
          <h3 className="font-semibold text-charcoal mb-3">Your attempts</h3>
          {history.length === 0 ? (
            <p className="text-sm text-bronze-dark/50">No attempts yet — pick a round above to start.</p>
          ) : (
            <div className="divide-y divide-border-subtle">
              {history.map((h, i) => (
                <div key={i} className="py-2.5 flex items-center justify-between text-sm">
                  <span className="text-charcoal font-medium">{h.title}</span>
                  <span className="text-bronze-dark/60">{h.questions} Q · {new Date(h.at).toLocaleDateString()}</span>
                  <span className={`font-semibold ${h.percentage >= 70 ? "text-success" : h.percentage >= 40 ? "text-warning" : "text-danger"}`}>
                    {h.percentage}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  /* ------------------------------ SETUP ----------------------------- */
  if (stage === "setup" && chosen) {
    const Icon = ICONS[chosen.id] ?? Brain;
    // With subjects, only the selected subjects' questions are available
    const maxCount = chosen.subject_counts
      ? subjects.reduce((n, sub) => n + (chosen.subject_counts?.[sub] ?? 0), 0)
      : chosen.available;
    const shown = Math.min(count, Math.max(1, maxCount));
    return (
      <div className="max-w-xl mx-auto surface-card p-8 animate-scale-in">
        <button onClick={() => setStage("home")} className="flex items-center gap-1.5 text-xs font-medium text-bronze-dark/50 hover:text-charcoal mb-5">
          <ArrowLeft className="w-3.5 h-3.5" /> All rounds
        </button>
        <div className="flex items-center gap-3 mb-6">
          <div className="w-11 h-11 rounded-[12px] bg-orange flex items-center justify-center"><Icon className="w-5 h-5 text-white" /></div>
          <div>
            <h2 className="type-h3">{chosen.title}</h2>
            <p className="text-sm text-bronze-dark/60">{chosen.description}</p>
          </div>
        </div>

        <div className="space-y-5">
          <label className="block">
            <span className="flex justify-between text-sm font-medium text-charcoal mb-2">
              Number of questions <span className="text-orange font-semibold">{shown}</span>
            </span>
            <input type="range" min={1} max={Math.max(1, maxCount)} value={shown} onChange={(e) => setCount(Number(e.target.value))}
              className="w-full accent-orange" />
            <span className="text-xs text-bronze-dark/50">1 – {maxCount} available{chosen.subjects ? " in the selected subjects" : ""}</span>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-charcoal mb-2 block">Timer</span>
            <div className="flex flex-wrap gap-2">
              {[5, 10, 15, 20, 30, 45, 60].map((m) => (
                <button key={m} type="button" onClick={() => setMinutes(m)}
                  className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${minutes === m ? "bg-orange text-white border-orange" : "border-border-default text-charcoal hover:border-orange"}`}>
                  {m} min
                </button>
              ))}
              <input type="number" min={1} max={180} value={minutes} onChange={(e) => setMinutes(Math.max(1, Math.min(180, Number(e.target.value) || 1)))}
                className="w-20 px-2 py-1.5 rounded-full border border-border-default text-sm text-center" aria-label="Custom minutes" />
            </div>
          </label>

          {chosen.subjects && (
            <div>
              <span className="text-sm font-medium text-charcoal mb-2 block">Subjects</span>
              <div className="flex flex-wrap gap-2">
                {chosen.subjects.map((s) => {
                  const on = subjects.includes(s);
                  return (
                    <button key={s} type="button"
                      onClick={() => setSubjects(on ? subjects.filter((x) => x !== s) : [...subjects, s])}
                      className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${on ? "bg-earth text-ivory border-earth" : "border-border-default text-charcoal hover:border-orange"}`}>
                      {s}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {error && <p className="text-sm text-danger flex items-center gap-2"><AlertCircle className="w-4 h-4" />{error}</p>}
          <PBButton size="lg" className="w-full" onClick={begin} disabled={busy || (chosen.subjects ? subjects.length === 0 : false)}>
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : `Start · ${shown} question${shown > 1 ? "s" : ""} in ${minutes} min`}
          </PBButton>
        </div>
      </div>
    );
  }

  /* ------------------------------ TEST ------------------------------ */
  if (stage === "test" && session) {
    const q = session.questions[current];
    const ans = answers[q.id];
    const answered = session.questions.filter((x) => {
      const a = answers[x.id];
      return session.kind === "coding" ? typeof a === "string" && a.trim() !== (x.starter_code ?? "").trim() : a !== undefined && a !== "";
    }).length;
    const low = secondsLeft <= 60;

    return (
      <div className="space-y-4 animate-fade-in">
        {/* Header bar */}
        <div className="surface-card px-5 py-3 flex items-center justify-between gap-4 sticky top-2 z-10">
          <div>
            <p className="font-semibold text-charcoal">{session.title}</p>
            <p className="text-xs text-bronze-dark/60">{answered} of {session.questions.length} answered</p>
          </div>
          <div className={`flex items-center gap-2 font-mono text-lg font-bold ${low ? "text-danger" : "text-charcoal"}`}>
            <Clock className="w-5 h-5" /> {fmt(Math.max(0, secondsLeft))}
          </div>
          <PBButton size="sm" onClick={() => { if (answered < session.questions.length && !confirm("Some questions are unanswered. Submit anyway?")) return; finish(); }} disabled={busy}>
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : "Submit"}
          </PBButton>
        </div>

        {/* Question navigator */}
        <div className="flex flex-wrap gap-2">
          {session.questions.map((x, i) => {
            const a = answers[x.id];
            const done = session.kind === "coding" ? typeof a === "string" && a.trim() !== (x.starter_code ?? "").trim() : a !== undefined && a !== "";
            return (
              <button key={x.id} onClick={() => setCurrent(i)}
                className={`w-9 h-9 rounded-full text-sm font-semibold border transition-colors ${
                  i === current ? "bg-orange text-white border-orange" : done ? "bg-success-light text-success border-success/30" : "bg-surface text-charcoal border-border-default"}`}>
                {i + 1}
              </button>
            );
          })}
        </div>

        {/* Question */}
        <div className="surface-card p-6 space-y-4">
          <p className="text-xs font-semibold text-orange uppercase tracking-wide">
            Question {current + 1}{q.topic ? ` · ${q.topic}` : ""}{q.difficulty ? ` · ${q.difficulty}` : ""}
          </p>

          {session.kind === "mcq" && (
            <>
              <p className="text-charcoal font-medium">{q.question}</p>
              <div className="space-y-2">
                {q.options?.map((o, i) => (
                  <button key={i} onClick={() => setAnswers({ ...answers, [q.id]: i })}
                    className={`w-full text-left px-4 py-3 rounded-[12px] border text-sm transition-colors ${
                      ans === i ? "border-orange bg-orange/8 text-charcoal font-medium" : "border-border-default hover:border-orange/40"}`}>
                    <span className="font-semibold mr-2">{String.fromCharCode(65 + i)}.</span>{o}
                  </button>
                ))}
              </div>
            </>
          )}

          {session.kind === "coding" && (
            <>
              <h3 className="font-semibold text-charcoal">{q.title}</h3>
              <p className="text-sm text-charcoal whitespace-pre-line">{q.description?.replace(/`/g, "")}</p>
              {q.examples?.map((ex, i) => (
                <p key={i} className="text-xs font-mono bg-ivory rounded-[8px] px-3 py-2 text-bronze-dark">Input: {ex.input} → Output: {ex.output}</p>
              ))}
              <textarea value={String(ans ?? "")} onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
                rows={14} spellCheck={false}
                className="w-full font-mono text-sm px-4 py-3 bg-earth text-ivory rounded-[12px] border border-border-default" />
              <p className="text-xs text-bronze-dark/50">Python 3. Your solution runs against hidden test cases when you submit.</p>
            </>
          )}

          {session.kind === "spoken" && (
            <>
              <p className="text-charcoal font-medium">{q.prompt}</p>
              <div className="flex items-center gap-3">
                {recording ? (
                  <PBButton variant="danger" size="sm" onClick={stopRecording}><MicOff className="w-4 h-4" /> Stop</PBButton>
                ) : (
                  <PBButton size="sm" onClick={() => startRecording(q.id)}><Mic className="w-4 h-4" /> Speak your answer</PBButton>
                )}
                {recording && <span className="text-sm text-danger flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-danger animate-pulse-soft" /> Listening… speak into your microphone</span>}
              </div>
              <textarea value={String(ans ?? "")} onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })} rows={6}
                placeholder="Your transcript appears here as you speak. (No microphone or speech recognition not working? You can type your answer directly in this box!)"
                className="w-full px-4 py-3 text-sm bg-surface border border-border-default rounded-[12px]" />
              <p className="text-xs text-bronze-dark/50">
                Speech recognition uses your browser's built-in speech engine (Google Chrome or Microsoft Edge recommended). You can also type or edit your transcript directly. NEXUS evaluates your answer's structure, vocabulary, and relevance.
              </p>
            </>
          )}

          {session.kind === "essay" && (
            <>
              <p className="text-charcoal font-medium">{q.prompt}</p>
              <textarea value={String(ans ?? "")} onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })} rows={14}
                placeholder="Write 200–300 words. Use paragraphs: introduction, arguments, conclusion."
                className="w-full px-4 py-3 text-sm bg-surface border border-border-default rounded-[12px] leading-relaxed" />
              <p className="text-xs text-bronze-dark/60">{wordCount(String(ans ?? ""))} words</p>
            </>
          )}

          {error && <p className="text-sm text-danger flex items-center gap-2"><AlertCircle className="w-4 h-4" />{error}</p>}

          <div className="flex justify-between pt-2">
            <PBButton variant="secondary" size="sm" disabled={current === 0} onClick={() => { stopRecording(); setCurrent(current - 1); }}>
              <ChevronLeft className="w-4 h-4" /> Previous
            </PBButton>
            <PBButton variant="secondary" size="sm" disabled={current === session.questions.length - 1}
              onClick={() => { stopRecording(); setCurrent(current + 1); }}>
              Next <ChevronRight className="w-4 h-4" />
            </PBButton>
          </div>
        </div>
      </div>
    );
  }

  /* ----------------------------- RESULT ----------------------------- */
  if (stage === "result" && result) {
    const pct = result.percentage;
    return (
      <div className="space-y-5 animate-fade-in">
        <div className="surface-card p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold text-orange uppercase tracking-wide mb-1">{result.title}</p>
            <h2 className="type-h2">{result.score} / {result.max_score} · {pct}%</h2>
            <p className="text-sm text-bronze-dark/60">
              {result.questions} question{result.questions > 1 ? "s" : ""} · {fmt(result.time_taken_seconds)} of {result.time_limit_minutes} min
              {result.submitted_late && " · submitted after time ran out"}
            </p>
          </div>
          <div className="flex gap-2">
            <PBButton variant="secondary" onClick={() => { setStage("home"); loadHome(); }}><ArrowLeft className="w-4 h-4" /> All rounds</PBButton>
            <PBButton onClick={() => chosen && openSetup(chosen)}><RotateCcw className="w-4 h-4" /> Try again</PBButton>
          </div>
        </div>

        {result.by_topic && (
          <div className="flex flex-wrap gap-2">
            {Object.entries(result.by_topic).map(([t, v]) => (
              <span key={t} className="text-xs font-semibold px-3 py-1 rounded-full bg-ivory-warm border border-bronze/15 text-charcoal">
                {t}: {v.correct}/{v.total}
              </span>
            ))}
          </div>
        )}

        {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
        {result.items.map((it: any, i: number) => (
          <div key={it.id} className="surface-card p-5 space-y-2">
            {result.kind === "mcq" && (
              <>
                <p className="font-medium text-charcoal flex items-start gap-2">
                  {it.correct ? <CheckCircle2 className="w-5 h-5 text-success shrink-0" /> : <XCircle className="w-5 h-5 text-danger shrink-0" />}
                  {i + 1}. {it.question}
                </p>
                <p className="text-sm pl-7">
                  Your answer: <b className={it.correct ? "text-success" : "text-danger"}>{it.your_answer === null ? "Not answered" : it.options[it.your_answer]}</b>
                  {!it.correct && <> · Correct: <b className="text-success">{it.options[it.correct_answer]}</b></>}
                </p>
                <p className="text-sm text-bronze-dark/70 pl-7">{it.explanation}</p>
              </>
            )}
            {result.kind === "coding" && (
              <>
                <p className="font-medium text-charcoal">{i + 1}. {it.title}</p>
                <p className="text-sm">{it.attempted ? `${it.passed} of ${it.total} hidden tests passed` : "Not attempted"}</p>
                <div className="flex gap-1.5">
                  {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                  {it.results.map((r: any) => (
                    <span key={r.test_case} title={r.error || ""} className={`w-6 h-6 rounded-full text-[11px] font-bold flex items-center justify-center ${r.passed ? "bg-success-light text-success" : "bg-danger-light text-danger"}`}>
                      {r.test_case}
                    </span>
                  ))}
                </div>
                {it.results.find((r: { error?: string }) => r.error) && (
                  <p className="text-xs font-mono text-danger">{it.results.find((r: { error?: string }) => r.error).error}</p>
                )}
              </>
            )}
            {(result.kind === "spoken" || result.kind === "essay") && (
              <>
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium text-charcoal">{i + 1}. {it.prompt}</p>
                  <span className="text-sm font-semibold text-orange">{it.score}/10</span>
                </div>
                {it.stats && (
                  <p className="text-xs text-bronze-dark/60">
                    {Object.entries(it.stats).filter(([, v]) => v !== null).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" · ")}
                  </p>
                )}
                {it.strengths?.length > 0 && <p className="text-sm text-success">✓ {it.strengths.join(" · ")}</p>}
                {it.improvements?.length > 0 && <p className="text-sm text-bronze-dark">To improve: {it.improvements.join(" · ")}</p>}
                <p className="text-xs text-bronze-dark/50">{it.ai_generated ? "[AI-generated feedback]" : it.note}</p>
              </>
            )}
          </div>
        ))}
      </div>
    );
  }

  return null;
}
