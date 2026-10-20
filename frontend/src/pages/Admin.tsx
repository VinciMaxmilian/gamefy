import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Navigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface Overview {
  days: number;
  totals: { users: number; premium_users: number; games: number; store_links: number };
  usage: { calls: number; cache_hits: number; cache_hit_rate: number | null; cost_usd: number; tokens: number };
  by_endpoint: { kind: string; endpoint: string; calls: number; cache_hits: number; tokens: number; cost_usd: number }[];
  per_user: { email: string; calls: number; cache_hits: number; cost_usd: number }[];
  daily: { day: string; calls: number; cost_usd: number }[];
  security_events: { action: string; count: number }[];
}
const usd = (n: number) => `$${n.toFixed(n < 1 ? 4 : 2)}`;

const Stat = ({ label, value, hint }: { label: string; value: string; hint?: string }) => (
  <div className="rounded-lg bg-surface p-5 shadow-card"><div className="text-sm text-fg-3">{label}</div><div className="mt-1 text-3xl font-semibold tracking-tight tabular-nums">{value}</div>{hint && <div className="mt-1 text-xs text-fg-3">{hint}</div>}</div>
);

function Table({ title, head, rows }: { title: string; head: string[]; rows: (string | number)[][] }) {
  return (
    <section className="space-y-3"><h2 className="text-xl">{title}</h2>
      <div className="overflow-x-auto rounded-lg bg-surface shadow-card">
        <table className="w-full min-w-[480px] text-left text-[15px]">
          <thead className="text-sm text-fg-3"><tr>{head.map((h, i) => <th key={h} className={cn("p-3 font-medium", i > 0 && "text-right")}>{h}</th>)}</tr></thead>
          <tbody>{rows.length === 0 ? <tr><td colSpan={head.length} className="p-4 text-fg-3">Nothing in this period.</td></tr> : rows.map((r, i) => (
            <tr key={i} className="border-t border-separator">{r.map((c, j) => <td key={j} className={cn("p-3 tabular-nums", j > 0 && "text-right", j === 0 && "break-all")}>{c}</td>)}</tr>))}</tbody>
        </table>
      </div>
    </section>
  );
}

/** Admin only. The server enforces the role; this page just hides itself from everyone else. */
export default function Admin() {
  const { me, loading } = useAuth();
  const [days, setDays] = useState(7);
  const q = useQuery({ queryKey: ["admin", days], queryFn: () => api<Overview>("/admin/overview", { query: { days } }), enabled: me?.role === "admin", refetchInterval: 60_000 });
  if (loading) return <div className="h-64" />;
  if (me?.role !== "admin") return <Navigate to="/" replace />;
  const d = q.data;
  const max = Math.max(1, ...(d?.daily.map((x) => x.calls) ?? [1]));
  return (
    <div className="space-y-10">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div><h1 className="text-4xl">Admin</h1><p className="mt-1 text-fg-2">Cost, cache and abuse signals.</p></div>
        <div className="flex gap-1 rounded-full bg-surface-2 p-1" role="group" aria-label="Period">
          {[1, 7, 30].map((n) => <button key={n} onClick={() => setDays(n)} aria-pressed={days === n} className={cn("rounded-full px-4 py-1.5 text-sm transition", days === n ? "bg-surface text-fg shadow-card" : "text-fg-2 hover:text-fg")}>{n === 1 ? "24 h" : `${n} days`}</button>)}
        </div>
      </header>
      {q.isLoading && <div className="h-40 animate-pulse rounded-lg bg-surface" />}
      {d && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Users" value={String(d.totals.users)} hint={`${d.totals.premium_users} premium`} />
            <Stat label="Games" value={String(d.totals.games)} hint={`${d.totals.store_links} store links`} />
            <Stat label="AI/API calls" value={String(d.usage.calls)} hint={`${d.usage.tokens.toLocaleString()} tokens`} />
            <Stat label="Cost" value={usd(d.usage.cost_usd)} hint={d.usage.cache_hit_rate === null ? "no calls yet" : `${Math.round(d.usage.cache_hit_rate * 100)}% cache hit rate`} />
          </div>
          {d.daily.length > 0 && (
            <section className="space-y-3"><h2 className="text-xl">Calls per day</h2>
              <div className="flex h-32 items-end gap-1.5 rounded-lg bg-surface p-4 shadow-card" role="img" aria-label="Calls per day">
                {d.daily.map((x) => <div key={x.day} title={`${x.day}: ${x.calls} calls, ${usd(x.cost_usd)}`} className="w-full max-w-12 flex-1 rounded-sm bg-accent/80" style={{ height: `${Math.max(4, (x.calls / max) * 100)}%` }} />)}
              </div></section>
          )}
          <Table title="Cost per user" head={["User", "Calls", "Cache hits", "Cost"]} rows={d.per_user.map((u) => [u.email, u.calls, u.cache_hits, usd(u.cost_usd)])} />
          <Table title="By endpoint" head={["Kind · endpoint", "Calls", "Cache hits", "Tokens", "Cost"]} rows={d.by_endpoint.map((e) => [`${e.kind} ${e.endpoint}`, e.calls, e.cache_hits, e.tokens, usd(e.cost_usd)])} />
          <Table title="Security & audit events" head={["Event", "Count"]} rows={d.security_events.map((s) => [s.action, s.count])} />
        </>
      )}
    </div>
  );
}
