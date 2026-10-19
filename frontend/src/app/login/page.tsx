"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  AlertCircle, ArrowLeft, Building2, CheckCircle2, GraduationCap, Loader2, Lock, Mail, ShieldCheck, User,
} from "lucide-react";
import { PBButton } from "@/components/ui/pb-button";
import { PBInput } from "@/components/ui/pb-input";
import { findMyRunId, getSessionUser, login, registerPlacementCell, registerStudent, signOut, type UserRole } from "@/lib/api";

type Portal = {
  role: UserRole;
  title: string;
  blurb: string;
  icon: typeof GraduationCap;
  home: string;
  canSignUp: boolean;
};

const PORTALS: Portal[] = [
  { role: "student", title: "Student", blurb: "Check your readiness, gaps and company matches.", icon: GraduationCap, home: "/onboarding", canSignUp: true },
  { role: "placement_officer", title: "Placement Cell", blurb: "Review plans, manage drives and publish results.", icon: Building2, home: "/officer", canSignUp: true },
  { role: "admin", title: "Admin", blurb: "Manage staff accounts and the audit log.", icon: ShieldCheck, home: "/admin", canSignUp: false },
];

const DELAYS = ["delay-100", "delay-200", "delay-300"];

export default function LoginPage() {
  const router = useRouter();
  const [selected, setSelected] = useState<Portal | null>(null);
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);
  const [current, setCurrent] = useState<{ name: string; role: string } | null>(null);

  // Coming from a protected page (e.g. /officer) opens the matching box
  useEffect(() => {
    const next = new URLSearchParams(window.location.search).get("next") || "";
    const match = next.startsWith("/admin") ? PORTALS[2] : next.startsWith("/officer") ? PORTALS[1] : null;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (match) setSelected(match);
    const user = getSessionUser();
    if (user) setCurrent({ name: user.full_name, role: PORTALS.find((p) => p.role === user.role)?.title ?? user.role });
  }, []);

  function choose(p: Portal | null) {
    setSelected(p);
    setMode("signin");
    setError("");
    setInfo("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setError("");
    setInfo("");
    setLoading(true);
    try {
      if (mode === "signup" && selected.role === "placement_officer") {
        const res = await registerPlacementCell(name.trim(), email.trim(), password);
        setInfo(res.message);
        setMode("signin");
        setPassword("");
        setLoading(false);
        return;
      }
      const user = mode === "signup"
        ? await registerStudent(name.trim(), email.trim(), password)
        : await login(email.trim(), password);
      if (user.role !== selected.role) {
        // The server decides the role; picking the wrong box just sends the user to the right one
        signOut();
        const right = PORTALS.find((p) => p.role === user.role);
        throw new Error(`This is a ${right?.title ?? user.role} account — sign in from the ${right?.title ?? "matching"} box.`);
      }
      const next = new URLSearchParams(window.location.search).get("next");
      const studentNext = user.role === "student" && next && next.startsWith("/")
        && !next.startsWith("/officer") && !next.startsWith("/admin");
      if (studentNext) return router.push(next);
      // Students who already have an assessment go straight to it
      if (user.role === "student" && mode === "signin" && await findMyRunId().catch(() => null)) {
        return router.push("/dashboard");
      }
      router.push(selected.home);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-ivory flex flex-col">
      <header className="px-6 py-4 flex items-center justify-between max-w-5xl mx-auto w-full">
        <Link href="/" className="flex items-center gap-2 text-bronze-dark/60 hover:text-charcoal transition-colors">
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm font-medium">Home</span>
        </Link>
        <span className="text-2xl font-medium text-charcoal font-stardom">NEXUS</span>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center px-6 py-10">
        {current && (
          <p className="mb-6 text-sm text-bronze-dark/70 bg-ivory-warm border border-bronze/15 rounded-full px-4 py-1.5">
            This tab is signed in as <b className="text-charcoal">{current.name}</b> ({current.role}). Signing in below switches this tab only.
          </p>
        )}
        {!selected ? (
          <div className="w-full max-w-4xl animate-fade-in">
            <div className="text-center mb-10">
              <h1 className="type-h2 mb-2">Sign in to NEXUS</h1>
              <p className="type-body text-bronze-dark/60">Choose how you use the portal.</p>
            </div>
            <div className="grid sm:grid-cols-3 gap-5">
              {PORTALS.map((p, i) => (
                <button
                  key={p.role}
                  type="button"
                  onClick={() => choose(p)}
                  className={`surface-card p-7 text-left group hover:-translate-y-1 hover:shadow-lg hover:border-orange/40 transition-all animate-slide-up ${DELAYS[i]}`}
                >
                  <div className="w-12 h-12 rounded-[14px] bg-ivory-warm border border-bronze/15 flex items-center justify-center mb-5 group-hover:bg-orange group-hover:border-orange transition-colors">
                    <p.icon className="w-5 h-5 text-bronze-dark group-hover:text-white transition-colors" />
                  </div>
                  <h2 className="font-semibold text-lg text-charcoal mb-1">{p.title}</h2>
                  <p className="text-sm text-bronze-dark/60">{p.blurb}</p>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div key={selected.role} className="w-full max-w-md surface-card p-8 shadow-lg animate-scale-in">
            <button type="button" onClick={() => choose(null)}
              className="flex items-center gap-1.5 text-xs font-medium text-bronze-dark/50 hover:text-charcoal transition-colors mb-5">
              <ArrowLeft className="w-3.5 h-3.5" /> Choose a different role
            </button>

            <div className="flex items-center gap-3 mb-6">
              <div className="w-11 h-11 rounded-[12px] bg-orange flex items-center justify-center">
                <selected.icon className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="type-h3">{selected.title}</h1>
                <p className="text-sm text-bronze-dark/60">
                  {mode === "signin" ? "Sign in to continue"
                    : selected.role === "student" ? "Create your student account" : "Request a Placement Cell account"}
                </p>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === "signup" && (
                <PBInput label="Full name" icon={<User className="w-4 h-4" />} required
                  value={name} onChange={(e) => setName(e.target.value)} />
              )}
              <PBInput label="Email" type="email" icon={<Mail className="w-4 h-4" />} required autoComplete="email"
                value={email} onChange={(e) => setEmail(e.target.value)} />
              <PBInput label="Password" type="password" icon={<Lock className="w-4 h-4" />} required
                autoComplete={mode === "signin" ? "current-password" : "new-password"}
                hint={mode === "signup" ? "(8+ chars, a capital and a digit)" : undefined}
                value={password} onChange={(e) => setPassword(e.target.value)} />

              {mode === "signup" && selected.role === "placement_officer" && (
                <p className="text-xs text-bronze-dark/60">
                  An administrator approves Placement Cell accounts before the first sign-in.
                </p>
              )}

              {error && (
                <div className="flex items-center gap-2 text-danger text-sm p-3 bg-danger-light rounded-[10px] border border-danger/15 font-medium">
                  <AlertCircle className="w-4 h-4 shrink-0" />{error}
                </div>
              )}
              {info && (
                <div className="flex items-center gap-2 text-success text-sm p-3 bg-success-light rounded-[10px] border border-success/20 font-medium">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />{info}
                </div>
              )}

              <PBButton type="submit" size="lg" className="w-full" disabled={loading}>
                {loading ? <Loader2 className="w-4 h-4 animate-spin" />
                  : mode === "signin" ? "Sign in" : selected.role === "student" ? "Create account" : "Request account"}
              </PBButton>
            </form>

            {selected.canSignUp ? (
              <p className="text-sm text-bronze-dark/60 text-center mt-6">
                {mode === "signin" ? "New here? " : "Already have an account? "}
                <button type="button" onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(""); setInfo(""); }}
                  className="font-semibold text-orange hover:underline">
                  {mode === "signin" ? "Create an account" : "Sign in"}
                </button>
              </p>
            ) : (
              <p className="text-xs text-bronze-dark/50 text-center mt-6">Admin accounts are created by an existing administrator.</p>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
