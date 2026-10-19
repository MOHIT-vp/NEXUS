"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Navbar } from "@/components/navigation/navbar";
import { ArrowRight, FileText, Code2, GraduationCap, Building2, Upload, Brain, BarChart3, Compass } from "lucide-react";
import { PBButton } from "@/components/ui/pb-button";
import { AnimatedPerson } from "@/components/ui/animated-person";
import { PlacementScorecard } from "@/components/ui/placement-scorecard";

export default function Home() {
  const [showPerson, setShowPerson] = useState(true);

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;
    
    if (showPerson) {
      timeoutId = setTimeout(() => setShowPerson(false), 10000); // 10s for person
    } else {
      timeoutId = setTimeout(() => setShowPerson(true), 3000); // 3s for scorecard
    }
    
    return () => clearTimeout(timeoutId);
  }, [showPerson]);

  return (
    <div className="min-h-screen bg-ivory">
      <Navbar />

      {/* ────────────────────────────────────────────
          HERO
      ──────────────────────────────────────────── */}
      <section className="relative pt-28 pb-20 lg:pt-36 lg:pb-28 overflow-hidden">
        {/* Ambient background lighting */}
        <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
          <div className="absolute top-[10%] right-[15%] w-[500px] h-[500px] rounded-full bg-orange/[0.04] blur-[120px]" />
          <div className="absolute bottom-[10%] left-[10%] w-[400px] h-[400px] rounded-full bg-bronze/[0.06] blur-[100px]" />
        </div>

        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
            {/* Left — Copy */}
            <div className="animate-slide-up">
              <div className="type-micro text-orange mb-6 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-orange animate-pulse-soft" />
                CAREER INTELLIGENCE PLATFORM
              </div>

              <h1 className="type-display mb-6">
                Turn your profile{" "}
                <br className="hidden sm:block" />
                into a{" "}
                <span className="text-accent-orange">placement strategy.</span>
              </h1>

              <p className="type-body-lg max-w-lg mb-10">
                NEXUS analyzes your resume, coding activity, academic profile
                and industry requirements to show exactly where you stand — and what
                to do next.
              </p>

              <div className="flex flex-col sm:flex-row gap-3">
                <Link href="/onboarding">
                  <PBButton size="lg" variant="primary">
                    Start your assessment
                    <ArrowRight className="w-4 h-4" />
                  </PBButton>
                </Link>
              </div>
            </div>

            {/* Right — Intelligence visualization */}
            <div className="relative animate-slide-up delay-200 hidden lg:block h-[500px] w-full">
              <div
                className={`absolute inset-0 flex items-center justify-center transition-all duration-1000 ${
                  showPerson ? "opacity-100 scale-100 pointer-events-auto" : "opacity-0 scale-95 pointer-events-none"
                }`}
              >
                <div className="h-full w-full max-h-[500px]">
                  <AnimatedPerson />
                </div>
              </div>
              
              <div
                className={`absolute inset-0 flex items-center justify-center transition-all duration-1000 ${
                  !showPerson ? "opacity-100 scale-100 pointer-events-auto" : "opacity-0 scale-95 pointer-events-none"
                }`}
              >
                <div className="transform scale-[0.85] origin-center">
                  <PlacementScorecard />
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ────────────────────────────────────────────
          TRUST STRIP
      ──────────────────────────────────────────── */}
      <section id="about" className="py-16 border-y border-border-subtle scroll-mt-24">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <p className="type-h2 text-center mb-12">
            One profile. Four intelligence layers.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {[
              { icon: FileText, label: "Resume", desc: "Skills & experience extraction" },
              { icon: Code2, label: "Coding", desc: "LeetCode & GitHub analysis" },
              { icon: GraduationCap, label: "Academic", desc: "CGPA & coursework signals" },
              { icon: Building2, label: "Industry Fit", desc: "Company requirement matching" },
            ].map((item) => (
              <div key={item.label} className="text-center">
                <div className="w-12 h-12 mx-auto mb-4 rounded-[14px] bg-surface-muted border border-border-subtle flex items-center justify-center">
                  <item.icon className="w-5 h-5 text-bronze-dark" />
                </div>
                <h3 className="font-semibold text-charcoal text-[0.9375rem] mb-1">{item.label}</h3>
                <p className="text-sm text-bronze-dark/60">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ────────────────────────────────────────────
          HOW IT WORKS
      ──────────────────────────────────────────── */}
      <section id="how-it-works" className="py-20 lg:py-28 scroll-mt-24">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="text-center mb-16">
            <p className="type-micro text-bronze mb-3">HOW IT WORKS</p>
            <h2 className="type-h1">Four steps to career clarity.</h2>
          </div>

          <div className="grid md:grid-cols-4 gap-6 lg:gap-10">
            {[
              { num: "01", title: "Upload", desc: "Resume + coding profile", icon: Upload },
              { num: "02", title: "Understand", desc: "AI extracts skills and evidence", icon: Brain },
              { num: "03", title: "Benchmark", desc: "Compare against industry roles", icon: BarChart3 },
              { num: "04", title: "Act", desc: "Get your personalized roadmap", icon: Compass },
            ].map((step, i) => (
              <div key={step.num} className="relative group">
                {/* Connector line */}
                {i < 3 && (
                  <div className="hidden md:block absolute top-8 left-full w-full h-px bg-border-default -z-10" />
                )}
                <div className="surface-card p-6 hover-lift">
                  <span className="type-data text-orange/60 text-2xl font-bold">{step.num}</span>
                  <div className="w-10 h-10 mt-4 mb-3 rounded-[10px] bg-orange/8 flex items-center justify-center">
                    <step.icon className="w-5 h-5 text-orange" />
                  </div>
                  <h3 className="font-semibold text-charcoal mb-1">{step.title}</h3>
                  <p className="text-sm text-bronze-dark/60">{step.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ────────────────────────────────────────────
          INTELLIGENCE SECTION
      ──────────────────────────────────────────── */}
      <section className="py-20 lg:py-28 bg-earth text-ivory">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="max-w-2xl mb-16">
            <p className="type-micro text-bronze-light mb-3">INTELLIGENCE</p>
            <h2 className="type-h1 text-ivory mb-4">
              Your placement readiness,
              <br />
              decoded.
            </h2>
            <p className="type-body text-ivory/60 mb-12">
              From placement score to skill gaps, company matches to your learning roadmap — every dimension of your career readiness, analyzed and actionable.
            </p>

            {/* Removed Scorecard from here as it is now in the Hero */}
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: "Placement Score", value: "0–100", desc: "Composite readiness metric" },
              { label: "Skill Gaps", value: "Identified", desc: "Critical to low priority" },
              { label: "Company Matches", value: "Ranked", desc: "By profile strength" },
              { label: "Learning Roadmap", value: "Personalized", desc: "Week-by-week plan" },
            ].map((card) => (
              <div
                key={card.label}
                className="rounded-[16px] bg-white/[0.06] border border-white/[0.08] p-6 hover:bg-white/[0.09] transition-colors"
              >
                <p className="type-micro text-bronze-light/70 mb-3">{card.label}</p>
                <p className="text-2xl font-bold text-ivory mb-1">{card.value}</p>
                <p className="text-sm text-ivory/40">{card.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ────────────────────────────────────────────
          FINAL CTA
      ──────────────────────────────────────────── */}
      <section className="py-20 lg:py-28">
        <div className="max-w-3xl mx-auto px-6 lg:px-8 text-center">
          <h2 className="type-h1 mb-6">
            Don&apos;t guess your readiness.
            <br />
            <span className="text-accent-orange">Measure it.</span>
          </h2>
          <p className="type-body-lg text-bronze-dark/60 mb-10 max-w-lg mx-auto">
            Upload your resume, connect your coding profile, and get an intelligence-backed career readiness report in minutes.
          </p>
          <Link href="/onboarding">
            <PBButton size="lg" variant="primary">
              Start your assessment
              <ArrowRight className="w-4 h-4" />
            </PBButton>
          </Link>
        </div>
      </section>

      {/* ────────────────────────────────────────────
          FOOTER
      ──────────────────────────────────────────── */}
      <footer id="contact" className="border-t border-border-subtle py-8 scroll-mt-24">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="text-2xl font-medium text-bronze-dark/60 font-stardom">
              NEXUS
            </span>
          </div>
          <p className="text-xs text-bronze-dark/40 text-center sm:text-right">
            Questions about your plan or account? Contact your college Placement Cell.
            <br />
            Career intelligence for placement readiness.
          </p>
        </div>
      </footer>
    </div>
  );
}
