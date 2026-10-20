import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { TasteItem } from "@/lib/types";
import { cn, label } from "@/lib/utils";
import { RequireAuth } from "./Auth";

interface Taste { likes: TasteItem[]; dislikes: TasteItem[] }
interface Hw { cpu?: string; gpu?: string; ram_gb?: number; vram_gb?: number; storage_gb?: number; os?: string; gpu_recognized?: boolean; cpu_recognized?: boolean }

function Bars({ items, negative }: { items: TasteItem[]; negative?: boolean }) {
  return (
    <ul className="space-y-3">
      {items.map((t) => (
        <li key={t.key} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1.5">
          <span className="capitalize">{label(t.label)} <span className="text-xs text-fg-3">{t.kind}</span></span>
          <span className="tabular-nums text-sm text-fg-2">{t.weight > 0 ? "+" : ""}{t.weight.toFixed(2)}</span>
          <div className="col-span-2 h-1.5 overflow-hidden rounded-full bg-surface-2"><div className={cn("h-full rounded-full transition-[width] duration-700 ease-[var(--ease-spring)]", negative ? "bg-negative" : "bg-accent")} style={{ width: `${Math.abs(t.weight) * 100}%` }} /></div>
        </li>
      ))}
    </ul>
  );
}

export default function Profile() {
  const { me, logout } = useAuth();
  const nav = useNavigate();
  const taste = useQuery({ queryKey: ["taste"], queryFn: () => api<Taste>("/me/taste"), enabled: !!me });
  const hw = useQuery({ queryKey: ["hardware"], queryFn: () => api<Hw>("/me/hardware"), enabled: !!me });
  const [form, setForm] = useState<Hw>({});
  useEffect(() => { if (hw.data) setForm(hw.data); }, [hw.data]);
  const save = useMutation({
    mutationFn: () => api<{ gpu_recognized: boolean; cpu_recognized: boolean }>("/me/hardware", { method: "PUT", body: {
      cpu: form.cpu || null, gpu: form.gpu || null, ram_gb: form.ram_gb || null, vram_gb: form.vram_gb ?? null, storage_gb: form.storage_gb || null, os: form.os || null } }),
    onSuccess: () => hw.refetch(),
  });
  const del = useMutation({ mutationFn: () => api("/me/account", { method: "DELETE" }), onSuccess: async () => { await logout(); nav("/"); } });
  const num = (k: keyof Hw) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [k]: e.target.value === "" ? undefined : Number(e.target.value) }));

  return (
    <RequireAuth>
      <div className="space-y-12">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div><h1 className="text-4xl">Your profile</h1><p className="mt-1 text-fg-2">{me?.email}</p></div>
          <div className="flex items-center gap-3"><Badge tone={me?.plan === "premium" ? "accent" : "neutral"} className="px-3 py-1 text-sm">{me?.plan === "premium" ? "✦ Premium" : "Free plan"}</Badge>
            {me && <span className="text-sm text-fg-3">{me.usage.smart_search_today}/{me.limits.smart_search_per_day} smart searches today</span>}</div>
        </header>

        <section className="space-y-5">
          <div><h2 className="text-2xl"><span className="spark">✦</span> Your taste</h2><p className="mt-1 text-fg-2">Built from your wishlist, library, ratings and what you skip. It fades over time, so it follows you.</p></div>
          {taste.data && taste.data.likes.length === 0 && taste.data.dislikes.length === 0 ? (
            <p className="rounded-lg bg-surface p-6 text-fg-2">Nothing yet. <Link to="/games" className="text-accent">Add a few games</Link> to your wishlist or library and rate the ones you know.</p>
          ) : (
            <div className="grid gap-6 md:grid-cols-2">
              <div className="rounded-lg bg-surface p-6 shadow-card"><h3 className="mb-4 text-lg">You lean towards</h3>{taste.data && <Bars items={taste.data.likes} />}</div>
              <div className="rounded-lg bg-surface p-6 shadow-card"><h3 className="mb-4 text-lg">Not really your thing</h3>{taste.data && taste.data.dislikes.length ? <Bars items={taste.data.dislikes} negative /> : <p className="text-fg-3">Skip games you don’t like to teach us.</p>}</div>
            </div>
          )}
        </section>

        <section className="space-y-5">
          <div><h2 className="text-2xl">Your PC</h2><p className="mt-1 text-fg-2">We compare requirements with rules, not guesses. Stored only for you.</p></div>
          <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }} className="grid gap-4 rounded-lg bg-surface p-6 shadow-card sm:grid-cols-2">
            <div><Label htmlFor="gpu">GPU</Label><Input id="gpu" maxLength={80} placeholder="e.g. RTX 3060" value={form.gpu ?? ""} onChange={(e) => setForm({ ...form, gpu: e.target.value })} />
              {hw.data?.gpu && <p className={cn("mt-1 text-xs", hw.data.gpu_recognized ? "text-positive" : "text-warning")}>{hw.data.gpu_recognized ? "Recognized" : "Not recognized — we’ll ignore GPU in checks"}</p>}</div>
            <div><Label htmlFor="cpu">CPU</Label><Input id="cpu" maxLength={80} placeholder="e.g. Ryzen 5 5600" value={form.cpu ?? ""} onChange={(e) => setForm({ ...form, cpu: e.target.value })} /></div>
            <div><Label htmlFor="ram">RAM (GB)</Label><Input id="ram" type="number" min={1} max={1024} value={form.ram_gb ?? ""} onChange={num("ram_gb")} /></div>
            <div><Label htmlFor="vram">VRAM (GB)</Label><Input id="vram" type="number" min={0} max={256} value={form.vram_gb ?? ""} onChange={num("vram_gb")} /></div>
            <div><Label htmlFor="st">Free storage (GB)</Label><Input id="st" type="number" min={0} value={form.storage_gb ?? ""} onChange={num("storage_gb")} /></div>
            <div><Label htmlFor="os">OS</Label><select id="os" value={form.os ?? ""} onChange={(e) => setForm({ ...form, os: e.target.value || undefined })} className="h-11 w-full rounded-md bg-surface-2 px-4 text-[15px] outline-none"><option value="">—</option><option value="windows">Windows</option><option value="linux">Linux</option><option value="macos">macOS</option></select></div>
            <div className="flex items-center gap-3 sm:col-span-2"><Button type="submit" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save hardware"}</Button>{save.isSuccess && <span className="text-sm text-positive">Saved</span>}{save.isError && <span className="text-sm text-negative">{errorMessage(save.error)}</span>}</div>
          </form>
        </section>

        <section className="space-y-3 border-t border-separator pt-8">
          <h2 className="text-lg">Account</h2>
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" onClick={() => logout().then(() => nav("/"))}>Log out</Button>
            <Button variant="danger" onClick={() => { if (confirm("Delete your account and all your data? This cannot be undone.")) del.mutate(); }}>Delete account & data</Button>
          </div>
        </section>
      </div>
    </RequireAuth>
  );
}
