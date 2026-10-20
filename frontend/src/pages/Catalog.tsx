import { useQuery } from "@tanstack/react-query";
import { SlidersHorizontal, X } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CardSkeletons, GameCardView } from "@/components/GameCardView";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Facets, Page } from "@/lib/types";
import { cn, label } from "@/lib/utils";

const PLATFORMS = ["pc", "ps5", "ps4", "xbox", "switch", "mac", "linux"];
const SORTS: [string, string][] = [["relevance", "Relevance"], ["rating", "Top rated"], ["newest", "Newest"], ["price_asc", "Price: low to high"], ["price_desc", "Price: high to low"], ["shortest", "Shortest"]];

export default function Catalog() {
  const [sp, setSp] = useSearchParams();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const get = (k: string) => sp.getAll(k);
  const q = sp.get("q") ?? "";
  const sort = sp.get("sort") ?? "relevance";
  const maxPrice = sp.get("max_price") ?? "";
  const limit = Math.min(Number(sp.get("limit") ?? 24) || 24, 48 * 4);

  const set = (k: string, vals: string[]) => setSp((p) => { p.delete(k); vals.forEach((v) => p.append(k, v)); p.delete("limit"); return p; }, { replace: true });
  const toggle = (k: string, v: string) => set(k, get(k).includes(v) ? get(k).filter((x) => x !== v) : [...get(k), v]);

  const facets = useQuery({ queryKey: ["facets"], queryFn: () => api<Facets>("/games/facets"), staleTime: 600_000 });
  const query = { q, genres: get("genres"), tags: get("tags"), features: get("features"), platforms: get("platforms"), max_price: maxPrice, min_rating: sp.get("min_rating") ?? "", sort, limit: Math.min(limit, 48), offset: Math.max(0, limit - 48) };
  const res = useQuery({ queryKey: ["games", sp.toString()], queryFn: () => api<Page>("/games", { query }), placeholderData: (p) => p });

  const active = ["genres", "tags", "features", "platforms"].flatMap((k) => get(k).map((v) => [k, v] as const));
  const Chip = ({ k, v, on }: { k: string; v: string; on: boolean }) => (
    <button onClick={() => toggle(k, v)} aria-pressed={on} className={cn("rounded-full px-3 py-1.5 text-sm capitalize transition", on ? "bg-accent text-white" : "bg-surface-2 text-fg-2 hover:bg-surface-3")}>{label(v)}</button>
  );

  const filters = (
    <div className="space-y-7">
      <Group title="Genre">{facets.data?.genres.slice(0, 14).map((f) => <Chip key={f.value} k="genres" v={f.value} on={get("genres").includes(f.value)} />)}</Group>
      <Group title="Platform">{PLATFORMS.map((p) => <Chip key={p} k="platforms" v={p} on={get("platforms").includes(p)} />)}</Group>
      <Group title="Experience">{facets.data?.tags.slice(0, 16).map((f) => <Chip key={f.value} k="tags" v={f.value} on={get("tags").includes(f.value)} />)}</Group>
      <Group title="Modes">{["single-player", "co-op", "multiplayer", "controller-support"].map((m) => <Chip key={m} k="features" v={m} on={get("features").includes(m)} />)}</Group>
      <Group title="Max price">
        {[["Free", "0"], ["$10", "1000"], ["$20", "2000"], ["$40", "4000"], ["Any", ""]].map(([l, v]) => (
          <button key={l} onClick={() => setSp((p) => { v ? p.set("max_price", v) : p.delete("max_price"); return p; }, { replace: true })}
            className={cn("rounded-full px-3 py-1.5 text-sm transition", maxPrice === v ? "bg-accent text-white" : "bg-surface-2 text-fg-2 hover:bg-surface-3")}>{l}</button>
        ))}
      </Group>
    </div>
  );

  return (
    <div className="grid gap-8 lg:grid-cols-[280px_1fr]">
      <aside className="hidden lg:block"><div className="sticky top-24 max-h-[calc(100vh-7rem)] overflow-y-auto pr-2">{filters}</div></aside>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="mr-auto text-3xl md:text-4xl">{q ? <>Results for “{q}”</> : "Store"}</h1>
          <Button variant="secondary" size="sm" className="lg:hidden" onClick={() => setFiltersOpen(true)}><SlidersHorizontal className="size-4" />Filters</Button>
          <label className="sr-only" htmlFor="sort">Sort</label>
          <select id="sort" value={sort} onChange={(e) => setSp((p) => { p.set("sort", e.target.value); return p; }, { replace: true })} className="h-9 rounded-full bg-surface-2 px-4 text-sm text-fg outline-none">
            {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        {active.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {active.map(([k, v]) => <button key={k + v} onClick={() => toggle(k, v)} className="inline-flex items-center gap-1 rounded-full bg-accent/15 px-3 py-1 text-sm capitalize text-accent">{label(v)}<X className="size-3.5" /></button>)}
            <button onClick={() => setSp({}, { replace: true })} className="px-2 text-sm text-fg-3 hover:text-fg">Clear all</button>
          </div>
        )}
        <p className="text-sm text-fg-3" aria-live="polite">{res.data ? `${res.data.total} games` : "Loading…"}</p>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {res.isLoading ? <CardSkeletons n={9} /> : res.data?.items.map((g) => <GameCardView key={g.slug} game={g} />)}
        </div>
        {res.data && res.data.items.length === 0 && <p className="py-20 text-center text-fg-2">Nothing matches those filters. Try removing one — or <a href={`/discover?q=${encodeURIComponent(q)}`} className="text-accent">describe it to ✦ smart search</a>.</p>}
        {res.data && res.data.total > limit && limit < 48 * 4 && (
          <div className="flex justify-center"><Button variant="secondary" onClick={() => setSp((p) => { p.set("limit", String(limit + 48)); return p; }, { replace: true })}>Show more</Button></div>
        )}
      </div>
      {filtersOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Filters">
          <div className="absolute inset-0 bg-black/60" onClick={() => setFiltersOpen(false)} />
          <div className="material absolute inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto rounded-t-xl p-6 pb-10">
            <div className="mb-5 flex items-center justify-between"><h2 className="text-xl">Filters</h2><Button variant="ghost" size="icon" aria-label="Close" onClick={() => setFiltersOpen(false)}><X /></Button></div>
            {filters}
            <Button className="mt-8 w-full" size="lg" onClick={() => setFiltersOpen(false)}>Show {res.data?.total ?? ""} games</Button>
          </div>
        </div>
      )}
    </div>
  );
}

const Group = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <div><h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-fg-3">{title}</h3><div className="flex flex-wrap gap-2">{children}</div></div>
);
