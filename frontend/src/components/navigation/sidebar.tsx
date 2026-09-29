"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Building2,
  Map,
  User,
  ArrowLeft,
  Code2,
  ShieldCheck,
} from "lucide-react";

const navItems = [
  { key: "overview", label: "Overview", icon: LayoutDashboard, href: "#overview" },
  { key: "perfection", label: "Resume Perfection", icon: ShieldCheck, href: "#perfection" },
  { key: "companies", label: "Company Matches", icon: Building2, href: "#companies" },
  { key: "roadmap", label: "Learning Roadmap", icon: Map, href: "#roadmap" },
  { key: "skills", label: "Skills & Profile", icon: User, href: "#skills" },
  { key: "coding", label: "Code Practice", icon: Code2, href: "#coding" },
];

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  studentName?: string;
}

export function Sidebar({ activeTab, onTabChange, studentName }: SidebarProps) {
  return (
    <aside className="hidden lg:flex flex-col w-[220px] h-screen sticky top-0 border-r border-border-default bg-surface-warm py-6 px-4">
      {/* Logo */}
      <Link href="/" className="flex items-center gap-2 mb-8 px-2">
        <span className="font-semibold text-charcoal text-2xl tracking-tight font-stardom">
          NEXUS
        </span>
      </Link>

      {/* Nav items */}
      <nav className="flex flex-col gap-1 flex-1">
        {navItems.map((item) => {
          const isActive = activeTab === item.key;
          const Icon = item.icon;
          return (
            <button
              key={item.key}
              onClick={() => onTabChange(item.key)}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-[10px] text-sm font-medium transition-all text-left",
                isActive
                  ? "bg-orange/8 text-orange border border-orange/15"
                  : "text-bronze-dark/70 hover:text-charcoal hover:bg-surface-muted"
              )}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* Bottom */}
      <div className="border-t border-border-default pt-4 mt-4 space-y-2">
        <Link
          href="/onboarding"
          className="flex items-center gap-3 px-3 py-2.5 rounded-[10px] text-sm font-medium text-bronze-dark/70 hover:text-charcoal hover:bg-surface-muted transition-all"
        >
          <ArrowLeft className="w-4 h-4" />
          Re-analyse
        </Link>
        {studentName && (
          <div className="px-3 py-2 flex items-center gap-3">
            <div className="w-7 h-7 rounded-full bg-bronze/15 flex items-center justify-center shrink-0">
              <span className="text-xs font-bold text-bronze-dark">
                {studentName.charAt(0).toUpperCase()}
              </span>
            </div>
            <span className="text-xs font-medium text-bronze-dark truncate">
              {studentName}
            </span>
          </div>
        )}
      </div>
    </aside>
  );
}
