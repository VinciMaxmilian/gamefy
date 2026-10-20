import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { Facets, TasteItem } from "@/lib/types";
import { cn, label } from "@/lib/utils";
import { RequireAuth } from "./Auth";

interface Taste { likes: TasteItem[]; dislikes: TasteItem[]; explicit: Record<string, number> }
interface Hw { cpu?: string; gpu?: string; ram_gb?: number; vram_gb?: number; storage_gb?: number; os?: string; gpu_recognized?: boolean; cpu_recognized?: boolean }

function Bars({ items, negative }: { items: TasteItem[]; negative?: boolean }) {
  const { t: tr } = useI18n();
  return (
    <ul className="space-y-3">
      {items.map((t) => (
        <li key={t.key} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1.5">
          <span>{label(t.key.split(":", 2)[1] ?? t.label)} <span className="text-xs text-fg-3">{tr(`taste.${t.kind}` as "taste.genre")}</span></span>
          <span className="tabular-nums text-sm text-fg-2">{t.weight > 0 ? "+" : ""}{t.weight.toFixed(2)}</span>
          <div className="col-span-2 h-1.5 overflow-hidden rounded-full bg-surface-2"><div className={cn("h-full rounded-full transition-[width] duration-700 ease-[var(--ease-spring)]", negative ? "bg-negative" : "bg-accent")} style={{ width: `${Math.abs(t.weight) * 100}%` }} /></div>
        </li>
      ))}
    </ul>
  );
}

export default function Profile() {
  const { t } = useI18n();
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
  const facets = useQuery({ queryKey: ["facets"], queryFn: () => api<Facets>("/games/facets"), staleTime: 600_000 });
  const [prefs, setPrefs] = useState<Record<string, 1 | -1>>({});
  useEffect(() => {
    const e = taste.data?.explicit ?? {};
    setPrefs(Object.fromEntries(Object.entries(e).filter(([k]) => k.startsWith("genre:")).map(([k, v]) => [k.slice(6), v > 0 ? 1 : -1])));
  }, [taste.data]);
  const cycle = (g: string) => setPrefs((p) => { const n = { ...p }; if (!n[g]) n[g] = 1; else if (n[g] === 1) n[g] = -1; else delete n[g]; return n; });
  const savePrefs = useMutation({
    mutationFn: () => api("/me/taste/explicit", { method: "PUT", body: {
      likes: Object.keys(prefs).filter((g) => prefs[g] === 1), dislikes: Object.keys(prefs).filter((g) => prefs[g] === -1) } }),
    onSuccess: () => Promise.all([taste.refetch(), invalidateRecs()]),
  });
  const qc = useQueryClient();
  const invalidateRecs = () => qc.invalidateQueries({ queryKey: ["for-you"] });
  const del = useMutation({ mutationFn: () => api("/me/account", { method: "DELETE" }), onSuccess: async () => { await logout(); nav("/"); } });
  const num = (k: keyof Hw) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [k]: e.target.value === "" ? undefined : Number(e.target.value) }));

  return (
    <RequireAuth>
      <div className="space-y-12">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div><h1 className="text-4xl">{t("profile.title")}</h1><p className="mt-1 text-fg-2">{me?.email}</p></div>
          <div className="flex items-center gap-3"><Badge tone={me?.plan === "premium" ? "accent" : "neutral"} className="px-3 py-1 text-sm">{me?.plan === "premium" ? t("profile.premium") : t("profile.free")}</Badge>
            {me && <span className="text-sm text-fg-3">{t("profile.searches", { used: me.usage.smart_search_today, max: me.limits.smart_search_per_day })}</span>}</div>
        </header>

        <section className="space-y-5">
          <div><h2 className="text-2xl"><span className="spark">✦</span> {t("profile.taste")}</h2><p className="mt-1 text-fg-2">{t("profile.taste_sub")}</p></div>
          {taste.data && taste.data.likes.length === 0 && taste.data.dislikes.length === 0 ? (
            <p className="rounded-lg bg-surface p-6 text-fg-2">{t("profile.nothing_a")}<Link to="/games" className="text-accent">{t("profile.nothing_link")}</Link>{t("profile.nothing_b")}</p>
          ) : (
            <div className="grid gap-6 md:grid-cols-2">
              <div className="rounded-lg bg-surface p-6 shadow-card"><h3 className="mb-4 text-lg">{t("profile.leans")}</h3>{taste.data && <Bars items={taste.data.likes} />}</div>
              <div className="rounded-lg bg-surface p-6 shadow-card"><h3 className="mb-4 text-lg">{t("profile.not_thing")}</h3>{taste.data && taste.data.dislikes.length ? <Bars items={taste.data.dislikes} negative /> : <p className="text-fg-3">{t("profile.skip_hint")}</p>}</div>
            </div>
          )}
        </section>

        <section className="space-y-4">
          <div><h2 className="text-2xl">{t("profile.direct")}</h2><p className="mt-1 text-fg-2">{t("profile.direct_sub")}</p></div>
          <div className="flex flex-wrap gap-2">
            {facets.data?.genres.slice(0, 18).map((f) => {
              const v = prefs[f.value];
              return (
                <button key={f.value} onClick={() => cycle(f.value)} aria-label={`${label(f.value)}: ${t(v === 1 ? "profile.liked" : v === -1 ? "profile.avoided" : "profile.neutral")}`}
                  className={cn("rounded-full px-4 py-2 text-sm transition", v === 1 ? "bg-accent text-white" : v === -1 ? "bg-negative/15 text-negative line-through" : "bg-surface-2 text-fg-2 hover:bg-surface-3")}>
                  {label(f.value)}
                </button>);
            })}
          </div>
          <div className="flex items-center gap-3"><Button onClick={() => savePrefs.mutate()} disabled={savePrefs.isPending}>{savePrefs.isPending ? t("saving") : t("profile.save_prefs")}</Button>{savePrefs.isSuccess && <span className="text-sm text-positive">{t("saved")}</span>}</div>
        </section>

        <section className="space-y-5">
          <div><h2 className="text-2xl">{t("profile.pc")}</h2><p className="mt-1 text-fg-2">{t("profile.pc_sub")}</p></div>
          <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }} className="grid gap-4 rounded-lg bg-surface p-6 shadow-card sm:grid-cols-2">
            <div><Label htmlFor="gpu">GPU</Label><Input id="gpu" maxLength={80} placeholder="e.g. RTX 3060" value={form.gpu ?? ""} onChange={(e) => setForm({ ...form, gpu: e.target.value })} />
              {hw.data?.gpu && <p className={cn("mt-1 text-xs", hw.data.gpu_recognized ? "text-positive" : "text-warning")}>{hw.data.gpu_recognized ? t("profile.recognized") : t("profile.not_recognized")}</p>}</div>
            <div><Label htmlFor="cpu">CPU</Label><Input id="cpu" maxLength={80} placeholder="e.g. Ryzen 5 5600" value={form.cpu ?? ""} onChange={(e) => setForm({ ...form, cpu: e.target.value })} /></div>
            <div><Label htmlFor="ram">RAM (GB)</Label><Input id="ram" type="number" min={1} max={1024} value={form.ram_gb ?? ""} onChange={num("ram_gb")} /></div>
            <div><Label htmlFor="vram">VRAM (GB)</Label><Input id="vram" type="number" min={0} max={256} value={form.vram_gb ?? ""} onChange={num("vram_gb")} /></div>
            <div><Label htmlFor="st">{t("profile.free_storage")}</Label><Input id="st" type="number" min={0} value={form.storage_gb ?? ""} onChange={num("storage_gb")} /></div>
            <div><Label htmlFor="os">OS</Label><select id="os" value={form.os ?? ""} onChange={(e) => setForm({ ...form, os: e.target.value || undefined })} className="h-11 w-full rounded-md bg-surface-2 px-4 text-[15px] outline-none"><option value="">—</option><option value="windows">Windows</option><option value="linux">Linux</option><option value="macos">macOS</option></select></div>
            <div className="flex items-center gap-3 sm:col-span-2"><Button type="submit" disabled={save.isPending}>{save.isPending ? t("saving") : t("profile.save_hw")}</Button>{save.isSuccess && <span className="text-sm text-positive">{t("saved")}</span>}{save.isError && <span className="text-sm text-negative">{errorMessage(save.error)}</span>}</div>
          </form>
        </section>

        <section className="space-y-3 border-t border-separator pt-8">
          <h2 className="text-lg">{t("profile.account")}</h2>
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" onClick={() => logout().then(() => nav("/"))}>{t("nav.logout")}</Button>
            <Button variant="danger" onClick={() => { if (confirm(t("profile.delete_confirm"))) del.mutate(); }}>{t("profile.delete")}</Button>
          </div>
        </section>
      </div>
    </RequireAuth>
  );
}
