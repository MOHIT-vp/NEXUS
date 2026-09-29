"use client";

import { cn } from "@/lib/utils";
import { LayoutDashboard, Building2, Map, User, Code2, ShieldCheck } from "lucide-react";

const navItems = [
  { key: "overview", label: "Overview", icon: LayoutDashboard },
  { key: "perfection", label: "Perfection", icon: ShieldCheck },
  { key: "companies", label: "Companies", icon: Building2 },
  { key: "roadmap", label: "Roadmap", icon: Map },
  { key: "skills", label: "Profile", icon: User },
  { key: "coding", label: "Code", icon: Code2 },
];

interface MobileNavProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export function MobileNav({ activeTab, onTabChange }: MobileNavProps) {
  return (
    <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-40 bg-surface/95 backdrop-blur-md border-t border-border-default px-2 pb-[env(safe-area-inset-bottom)]">
      <div className="flex items-center justify-around py-2">
        {navItems.map((item) => {
          const isActive = activeTab === item.key;
          const Icon = item.icon;
          return (
            <button
              key={item.key}
              onClick={() => onTabChange(item.key)}
              className={cn(
                "flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-lg transition-all min-w-[64px]",
                isActive
                  ? "text-orange"
                  : "text-bronze-dark/50"
              )}
            >
              <Icon className="w-5 h-5" />
              <span className="text-[10px] font-semibold">{item.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
