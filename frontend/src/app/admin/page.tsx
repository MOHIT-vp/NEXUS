"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AlertCircle, Loader2, Lock, Mail, User } from "lucide-react";
import { PBBadge } from "@/components/ui/pb-badge";
import { PBButton } from "@/components/ui/pb-button";
import { PBInput } from "@/components/ui/pb-input";
import {
  AdminAccount, AdminStats, AuditEntry,
  createStaffAccount, getAdminStats, getAuditLog, getSessionUser, listAccounts, setAccountActive, signOut,
} from "@/lib/api";

const ROLE_LABEL: Record<string, string> = { student: "Student", placement_officer: "Placement Cell", admin: "Admin" };

export default function AdminPage() {
  const router = useRouter();
  const [me, setMe] = useState<string | null>(null);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [accounts, setAccounts] = useState<AdminAccount[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [form, setForm] = useState({ full_name: "", email: "", password: "", role: "placement_officer" as "placement_officer" | "admin" });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(async () => {
    const [s, a, l] = await Promise.all([getAdminStats(), listAccounts(), getAuditLog(50)]);
    setStats(s);
    setAccounts(a);
    setAudit(l);
  }, []);

  useEffect(() => {
    const user = getSessionUser();
    if (!user || user.role !== "admin") {
      router.replace("/login?next=/admin");
      return;
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMe(user.id);
    load().catch((e) => setNotice({ ok: false, text: e instanceof Error ? e.message : "Could not load." }));
  }, [router, load]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setNotice(null);
    try {
      const created = await createStaffAccount({ ...form, email: form.email.trim(), full_name: form.full_name.trim() });
      setNotice({ ok: true, text: `Account created for ${created.email}. Share the password with them securely.` });
      setForm({ full_name: "", email: "", password: "", role: "placement_officer" });
      await load();
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : "Could not create the account." });
    } finally {
      setBusy(false);
    }
  }

  async function toggle(a: AdminAccount) {
    try {
      await setAccountActive(a.id, !a.is_active);
      await load();
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : "Could not update the account." });
    }
  }

  if (!me) return <div className="min-h-screen bg-ivory" />;

  return (
    <div className="min-h-screen bg-ivory">
      <header className="border-b border-border-subtle bg-surface/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 lg:px-8 py-5 flex items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Link href="/" className="text-2xl font-semibold text-charcoal font-stardom">NEXUS</Link>
              <span className="text-bronze-dark/30 mx-1">·</span>
              <PBBadge variant="medium">Admin</PBBadge>
            </div>
            <h1 className="type-h2">System administration</h1>
            <p className="type-body text-bronze-dark/50 mt-1">Manage Placement Cell accounts and review the audit trail. Plan approvals stay with the Placement Cell.</p>
          </div>
          <button onClick={() => { signOut(); router.push("/login"); }}
            className="text-sm font-medium text-bronze-dark/60 hover:text-charcoal transition-colors">
            Sign out
          </button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 lg:px-8 py-8 space-y-8 animate-fade-in">
        {notice && (
          <div className={`text-sm p-3 rounded-[10px] border font-medium ${notice.ok ? "bg-success-light text-success border-success/20" : "bg-danger-light text-danger border-danger/15"}`}>
            {notice.text}
          </div>
        )}

        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              ["Pipeline runs", stats.total_workflow_runs],
              ["Awaiting review", stats.pending_review],
              ["Failed checks", stats.validation_failed],
              ["Published plans", stats.published_versions],
            ].map(([label, value]) => (
              <div key={label as string} className="surface-card p-5">
                <p className="text-xs text-bronze-dark/50 font-medium">{label}</p>
                <p className="text-2xl font-semibold text-charcoal mt-1">{value}</p>
              </div>
            ))}
          </div>
        )}

        <div className="grid lg:grid-cols-3 gap-6">
          <form onSubmit={handleCreate} className="surface-card p-6 space-y-4">
            <h2 className="type-h3">New staff account</h2>
            <PBInput label="Full name" icon={<User className="w-4 h-4" />} required
              value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            <PBInput label="Email" type="email" icon={<Mail className="w-4 h-4" />} required
              value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            <PBInput label="Temporary password" type="password" icon={<Lock className="w-4 h-4" />} required
              autoComplete="new-password" hint="(8+ chars, a capital and a digit)"
              value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <label className="block text-sm font-medium text-charcoal">
              Role
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as "placement_officer" | "admin" })}
                className="mt-1 w-full rounded-[10px] border border-border-default bg-surface px-3 py-2 text-sm">
                <option value="placement_officer">Placement Cell</option>
                <option value="admin">Admin</option>
              </select>
            </label>
            <PBButton type="submit" className="w-full" disabled={busy}>
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : "Create account"}
            </PBButton>
          </form>

          <div className="surface-card p-6 lg:col-span-2 overflow-x-auto">
            <h2 className="type-h3 mb-4">Accounts</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-bronze-dark/50">
                  <th className="pb-2 font-medium">Name</th><th className="pb-2 font-medium">Email</th>
                  <th className="pb-2 font-medium">Role</th><th className="pb-2 font-medium">Status</th><th />
                </tr>
              </thead>
              <tbody>
                {accounts.map((a) => (
                  <tr key={a.id} className="border-t border-border-subtle">
                    <td className="py-2 text-charcoal">{a.full_name}</td>
                    <td className="py-2 text-bronze-dark/70">{a.email}</td>
                    <td className="py-2">{ROLE_LABEL[a.role] ?? a.role}</td>
                    <td className="py-2"><PBBadge variant={a.is_active ? "success" : "low"}>{a.is_active ? "Active" : "Inactive"}</PBBadge></td>
                    <td className="py-2 text-right">
                      {a.id !== me && (
                        <button onClick={() => toggle(a)} className="text-xs font-semibold text-orange hover:underline">
                          {a.is_active ? "Deactivate" : "Activate"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="surface-card p-6 overflow-x-auto">
          <h2 className="type-h3 mb-4">Recent activity (audit log)</h2>
          {audit.length === 0 ? (
            <p className="text-sm text-bronze-dark/50 flex items-center gap-2"><AlertCircle className="w-4 h-4" /> No activity yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-bronze-dark/50">
                  <th className="pb-2 font-medium">When</th><th className="pb-2 font-medium">Who</th>
                  <th className="pb-2 font-medium">Action</th><th className="pb-2 font-medium">On</th>
                </tr>
              </thead>
              <tbody>
                {audit.map((e) => (
                  <tr key={e.id} className="border-t border-border-subtle align-top">
                    <td className="py-2 text-bronze-dark/60 whitespace-nowrap">{e.timestamp ? new Date(e.timestamp).toLocaleString() : "—"}</td>
                    <td className="py-2">{e.agent ? `${e.agent} (agent)` : e.actor}</td>
                    <td className="py-2 font-medium text-charcoal">{e.action}</td>
                    <td className="py-2 text-bronze-dark/60">{e.entity_type ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </div>
  );
}
