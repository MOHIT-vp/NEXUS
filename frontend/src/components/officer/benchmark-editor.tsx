"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Loader2, Plus, Trash2 } from "lucide-react";
import { PBButton } from "@/components/ui/pb-button";
import {
  addBenchmark, listBenchmarks, removeBenchmark, updateBenchmark,
  type BenchmarkItem, type BenchmarkRole,
} from "@/lib/api";

const LEVELS = ["beginner", "intermediate", "advanced", "expert"];
const selectCls = "rounded-[8px] border border-border-default bg-surface px-2 py-1 text-sm";

/** Placement Cell edits what each target role requires; the next analysis uses it. */
export function BenchmarkEditor() {
  const [roles, setRoles] = useState<BenchmarkRole[]>([]);
  const [roleKey, setRoleKey] = useState("");
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [draft, setDraft] = useState({ skill: "", expected_level: "intermediate", importance: "required", source: "" });

  const load = useCallback(async () => {
    const data = await listBenchmarks();
    setRoles(data);
    setRoleKey((k) => k || data[0]?.role_key || "");
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load().catch((e) => setNotice({ ok: false, text: e instanceof Error ? e.message : "Could not load benchmarks." }));
  }, [load]);

  const role = roles.find((r) => r.role_key === roleKey);

  async function change(item: BenchmarkItem, patch: Partial<BenchmarkItem>) {
    setSavingId(item.id);
    setNotice(null);
    try {
      await updateBenchmark(item.id, { expected_level: patch.expected_level, importance: patch.importance, source: item.source ?? undefined });
      await load();
      setNotice({ ok: true, text: `${item.skill} updated — applies to the next analysis.` });
    } catch (e) {
      setNotice({ ok: false, text: e instanceof Error ? e.message : "Could not save." });
    } finally {
      setSavingId(null);
    }
  }

  async function remove(item: BenchmarkItem) {
    if (!confirm(`Remove ${item.skill} from ${role?.title}?`)) return;
    setSavingId(item.id);
    try {
      await removeBenchmark(item.id);
      await load();
      setNotice({ ok: true, text: `${item.skill} removed.` });
    } catch (e) {
      setNotice({ ok: false, text: e instanceof Error ? e.message : "Could not remove." });
    } finally {
      setSavingId(null);
    }
  }

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.skill.trim()) return;
    setSavingId("new");
    setNotice(null);
    try {
      await addBenchmark(roleKey, { ...draft, skill: draft.skill.trim(), source: draft.source.trim() || undefined });
      setDraft({ skill: "", expected_level: "intermediate", importance: "required", source: "" });
      await load();
      setNotice({ ok: true, text: "Skill added — applies to the next analysis." });
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : "Could not add." });
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="type-h3">Skill benchmark library</h2>
        <p className="text-sm text-bronze-dark/60">
          What each target role requires. The Skill Gap Agent measures every student against these on the next analysis; every change is recorded in the audit log.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {roles.map((r) => (
          <button key={r.role_key} onClick={() => setRoleKey(r.role_key)}
            className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${r.role_key === roleKey ? "bg-orange text-white border-orange" : "border-border-default text-charcoal hover:border-orange"}`}>
            {r.title} <span className="opacity-70">({r.skills.length})</span>
          </button>
        ))}
      </div>

      {notice && (
        <div className={`text-sm p-3 rounded-[10px] border font-medium flex items-center gap-2 ${notice.ok ? "bg-success-light text-success border-success/20" : "bg-danger-light text-danger border-danger/15"}`}>
          {!notice.ok && <AlertCircle className="w-4 h-4" />}{notice.text}
        </div>
      )}

      {role && (
        <div className="surface-card p-5 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-bronze-dark/50">
                <th className="pb-2 font-medium">Skill</th><th className="pb-2 font-medium">Level expected</th>
                <th className="pb-2 font-medium">Importance</th><th className="pb-2 font-medium">Source</th><th />
              </tr>
            </thead>
            <tbody>
              {role.skills.map((b) => (
                <tr key={b.id} className="border-t border-border-subtle">
                  <td className="py-2 font-medium text-charcoal">{b.skill}</td>
                  <td className="py-2">
                    <select value={b.expected_level} disabled={savingId === b.id} className={selectCls}
                      onChange={(e) => change(b, { expected_level: e.target.value as BenchmarkItem["expected_level"] })}>
                      {LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
                    </select>
                  </td>
                  <td className="py-2">
                    <select value={b.importance} disabled={savingId === b.id} className={selectCls}
                      onChange={(e) => change(b, { importance: e.target.value as BenchmarkItem["importance"] })}>
                      <option value="required">required</option>
                      <option value="preferred">preferred</option>
                    </select>
                  </td>
                  <td className="py-2 text-xs text-bronze-dark/60 max-w-[220px] truncate" title={b.source ?? ""}>{b.source}</td>
                  <td className="py-2 text-right">
                    {savingId === b.id ? <Loader2 className="w-4 h-4 animate-spin inline text-bronze" /> : (
                      <button onClick={() => remove(b)} className="text-bronze-dark/40 hover:text-danger" aria-label={`Remove ${b.skill}`}>
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <form onSubmit={add} className="mt-4 pt-4 border-t border-border-subtle flex flex-wrap items-center gap-2">
            <input value={draft.skill} onChange={(e) => setDraft({ ...draft, skill: e.target.value })} placeholder="Add a skill (e.g. Rust)"
              className="flex-1 min-w-[160px] rounded-[8px] border border-border-default bg-surface px-3 py-1.5 text-sm" />
            <select value={draft.expected_level} onChange={(e) => setDraft({ ...draft, expected_level: e.target.value })} className={selectCls}>
              {LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
            <select value={draft.importance} onChange={(e) => setDraft({ ...draft, importance: e.target.value })} className={selectCls}>
              <option value="required">required</option>
              <option value="preferred">preferred</option>
            </select>
            <input value={draft.source} onChange={(e) => setDraft({ ...draft, source: e.target.value })} placeholder="Source (optional)"
              className="w-44 rounded-[8px] border border-border-default bg-surface px-3 py-1.5 text-sm" />
            <PBButton type="submit" size="sm" disabled={savingId === "new" || !draft.skill.trim()}>
              <Plus className="w-4 h-4" /> Add
            </PBButton>
          </form>
        </div>
      )}
    </div>
  );
}
