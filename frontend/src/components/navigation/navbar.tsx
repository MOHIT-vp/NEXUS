"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { liquidGlass } from "@/lib/liquid-glass";
import { cn } from "@/lib/utils";
import { getSessionUser, signOut, type SessionUser } from "@/lib/api";

const NAV_LINKS = [
  { label: "Home", href: "/" },
  { label: "About", href: "/#about" },
  { label: "How it works", href: "/#how-it-works" },
  { label: "Contact", href: "/#contact" },
];

const ROLE_LABEL: Record<string, string> = {
  student: "Student",
  placement_officer: "Placement Cell",
  admin: "Admin",
};

const HOME_FOR_ROLE: Record<string, string> = {
  student: "/dashboard",
  placement_officer: "/officer",
  admin: "/admin",
};

export function Navbar() {
  const glassRef = useRef<HTMLDivElement>(null);
  const [scrolled, setScrolled] = useState(false);
  const [user, setUser] = useState<SessionUser | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setUser(getSessionUser()), 0);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    const el = glassRef.current;
    if (!el) return;
    const instance = liquidGlass(el, {
      scale: -60,
      chroma: 3,
      border: 0.05,
      mapBlur: 8,
      blur: 6,
      saturate: 1.2,
      fallbackBlur: 12,
    });
    return () => instance.destroy();
  }, []);

  return (
    <header className="fixed top-0 left-0 right-0 z-50 flex justify-center px-4 pt-4">
      <nav
        ref={glassRef}
        className={cn(
          "liquid-glass rounded-[20px] px-6 py-3 grid grid-cols-[1fr_auto] md:grid-cols-[1fr_auto_1fr] items-center gap-6 max-w-5xl w-full",
          "transition-all duration-300",
          scrolled && "shadow-lg"
        )}
      >
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 justify-self-start">
          <span className="font-semibold text-charcoal text-2xl tracking-tight font-stardom">
            NEXUS
          </span>
        </Link>

        {/* Center: page links */}
        <div className="hidden md:flex items-center justify-center gap-8">
          {NAV_LINKS.map((l) => (
            <Link key={l.label} href={l.href}
              className="text-sm text-bronze-dark/70 hover:text-charcoal transition-colors">
              {l.label}
            </Link>
          ))}
        </div>

        {/* Right: account */}
        <div className="flex items-center justify-end gap-4">
          {user ? (
            <>
              <Link href={HOME_FOR_ROLE[user.role] ?? "/dashboard"} title="Open my workspace"
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-ivory-warm border border-bronze/15 text-sm hover:border-orange transition-colors">
                <span className="text-[11px] font-bold uppercase tracking-wide text-orange whitespace-nowrap">{ROLE_LABEL[user.role] ?? user.role}</span>
                <span className="hidden lg:inline font-medium text-charcoal max-w-[140px] truncate">{user.full_name}</span>
              </Link>
              <button
                onClick={() => { signOut(); setUser(null); }}
                className="text-sm text-bronze-dark/70 hover:text-charcoal transition-colors whitespace-nowrap"
              >
                Sign out
              </button>
            </>
          ) : (
            <Link href="/login"
              className="inline-flex items-center px-5 py-2 text-sm font-semibold text-charcoal border border-border-default rounded-full hover:bg-orange hover:border-orange hover:text-white transition-colors">
              Sign in
            </Link>
          )}
        </div>
      </nav>
    </header>
  );
}
