import { useQuery } from "@tanstack/react-query";
import { SlidersHorizontal, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CardSkeletons, GameCardView } from "@/components/GameCardView";
import { Pagination } from "@/components/Pagination";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Facets, Page } from "@/lib/types";
import { cn, label } from "@/lib/utils";

const PAGE_SIZE = 24;
const PLATFORMS = ["pc", "ps5", "ps4", "xbox", "switch", "mac", "linux"];
const SORTS = ["relevance", "rating", "newest", "price_asc", "price_desc", "shortest"] as const;
const PRICES = [["filter.free", "0"], ["$10", "1000"], ["$20", "2000"], ["$40", "4000"], ["filter.any", ""]] as const;

export default function Catalog() {
  const { t, lang } = useI18n();
  const [sp, setSp] = useSearchParams();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const get = (k: string) => sp.getAll(k);
  const q = sp.get("q") ?? "";
  const sort = sp.get("sort") ?? "relevance";
  const maxPrice = sp.get("max_price") ?? "";
  const page = Math.max(1, Number(sp.get("page")) || 1);

  // Any change to the query resets to page 1.
  const update = (fn: (p: URLSearchParams) => void) => setSp((p) => { fn(p); p.delete("page"); return p; }, { replace: true });
  const toggle = (k: string, v: string) => update((p) => { const cur = p.getAll(k); p.delete(k); (cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v]).forEach((x) => p.append(k, x)); });
  const goPage = (n: number) => { setSp((p) => { n > 1 ? p.set("page", String(n)) : p.delete("page"); return p; }, { replace: true }); window.scrollTo({ top: 0, behavior: "smooth" }); };

  const facets = useQuery({ queryKey: ["facets"], queryFn: () => api<Facets>("/games/facets"), staleTime: 600_000 });
  const query = { q, genres: get("genres"), tags: get("tags"), features: get("features"), platforms: get("platforms"), max_price: maxPrice, min_rating: sp.get("min_rating") ?? "", sort, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE };
  const res = useQuery({ queryKey: ["games", sp.toString()], queryFn: () => api<Page>("/games", { query }), placeholderData: (p) => p });

  const total = res.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  useEffect(() => { if (res.data && page > pages) goPage(pages); }, [res.data, page, pages]); // eslint-disable-line react-hooks/exhaustive-deps

  const active = ["genres", "tags", "features", "platforms"].flatMap((k) => get(k).map((v) => [k, v] as const));
  const hasFilters = active.length > 0 || !!q || !!maxPrice;
  const from = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const to = Math.min(page * PAGE_SIZE, total);
  const Chip = ({ k, v, on }: { k: string; v: string; on: boolean }) => (
    <button onClick={() => toggle(k, v)} aria-pressed={on} className={cn("rounded-full px-3 py-1.5 text-sm transition", on ? "bg-accent text-white" : "bg-surface-2 text-fg-2 hover:bg-surface-3")}>{label(v)}</button>
  );

  const filters = (
    <div className="space-y-7">
      <Group title={t("filter.genre")}>{facets.data?.genres.slice(0, 14).map((f) => <Chip key={f.value} k="genres" v={f.value} on={get("genres").includes(f.value)} />)}</Group>
      <Group title={t("filter.platform")}>{PLATFORMS.map((p) => <Chip key={p} k="platforms" v={p} on={get("platforms").includes(p)} />)}</Group>
      <Group title={t("filter.experience")}>{facets.data?.tags.slice(0, 16).map((f) => <Chip key={f.value} k="tags" v={f.value} on={get("tags").includes(f.value)} />)}</Group>
      <Group title={t("filter.modes")}>{["single-player", "co-op", "multiplayer", "controller-support"].map((m) => <Chip key={m} k="features" v={m} on={get("features").includes(m)} />)}</Group>
      <Group title={t("filter.max_price")}>
        {PRICES.map(([l, v]) => (
          <button key={l} onClick={() => update((p) => { v ? p.set("max_price", v) : p.delete("max_price"); })}
            className={cn("rounded-full px-3 py-1.5 text-sm transition", maxPrice === v ? "bg-accent text-white" : "bg-surface-2 text-fg-2 hover:bg-surface-3")}>{l.startsWith("filter.") ? t(l as "filter.free") : l}</button>
        ))}
      </Group>
    </div>
  );

  return (
    <div className="grid gap-8 lg:grid-cols-[280px_1fr]">
      <aside className="hidden lg:block"><div className="sticky top-24 max-h-[calc(100vh-7rem)] overflow-y-auto pr-2">{filters}</div></aside>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="mr-auto text-3xl md:text-4xl">{q ? t("store.results_for", { q }) : t("store.title")}</h1>
          <Button variant="secondary" size="sm" className="lg:hidden" onClick={() => setFiltersOpen(true)}><SlidersHorizontal className="size-4" />{t("store.filters")}</Button>
          <label className="sr-only" htmlFor="sort">{t("store.sort")}</label>
          <select id="sort" value={sort} onChange={(e) => update((p) => { p.set("sort", e.target.value); })} className="h-9 rounded-full bg-surface-2 px-4 text-sm text-fg outline-none">
            {SORTS.map((v) => <option key={v} value={v}>{t(`sort.${v}`)}</option>)}
          </select>
        </div>
        {active.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {active.map(([k, v]) => <button key={k + v} onClick={() => toggle(k, v)} className="inline-flex items-center gap-1 rounded-full bg-accent/15 px-3 py-1 text-sm text-accent">{label(v)}<X className="size-3.5" /></button>)}
            <button onClick={() => setSp({}, { replace: true })} className="px-2 text-sm text-fg-3 hover:text-fg">{t("store.clear_all")}</button>
          </div>
        )}
        <p className="text-sm text-fg-3" aria-live="polite">
          {res.data ? (total > 0 ? `${t("store.count", { n: total.toLocaleString(lang) })} · ${t("store.showing", { from, to, total })}` : t("store.count", { n: 0 })) : t("loading")}
        </p>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {res.isLoading ? <CardSkeletons n={9} /> : res.data?.items.map((g) => <GameCardView key={g.slug} game={g} />)}
        </div>
        {res.data && res.data.items.length === 0 && hasFilters && (
          <p className="py-20 text-center text-fg-2">{t("store.empty_a")}<Link to={`/discover?q=${encodeURIComponent(q)}`} className="text-accent">{t("store.empty_link")}</Link>{t("store.empty_b")}</p>
        )}
        <Pagination page={Math.min(page, pages)} pages={pages} onPage={goPage} />
      </div>
      {filtersOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label={t("store.filters")}>
          <div className="absolute inset-0 bg-black/60" onClick={() => setFiltersOpen(false)} />
          <div className="material absolute inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto rounded-t-xl p-6 pb-10">
            <div className="mb-5 flex items-center justify-between"><h2 className="text-xl">{t("store.filters")}</h2><Button variant="ghost" size="icon" aria-label={t("close")} onClick={() => setFiltersOpen(false)}><X /></Button></div>
            {filters}
            <Button className="mt-8 w-full" size="lg" onClick={() => setFiltersOpen(false)}>{t("store.show_games", { n: total || "" })}</Button>
          </div>
        </div>
      )}
    </div>
  );
}

const Group = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <div><h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-fg-3">{title}</h3><div className="flex flex-wrap gap-2">{children}</div></div>
);
