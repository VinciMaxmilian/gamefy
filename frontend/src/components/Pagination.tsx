import { ChevronLeft, ChevronRight } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/** 1 … 4 5 [6] 7 8 … 20 — always first, last and the neighbours of the current page. */
export function pageItems(page: number, pages: number): (number | "gap")[] {
  const keep = new Set([1, pages, page - 1, page, page + 1].filter((n) => n >= 1 && n <= pages));
  const sorted = [...keep].sort((a, b) => a - b);
  const out: (number | "gap")[] = [];
  sorted.forEach((n, i) => { if (i > 0 && n - sorted[i - 1] > 1) out.push("gap"); out.push(n); });
  return out;
}

export function Pagination({ page, pages, onPage }: { page: number; pages: number; onPage: (n: number) => void }) {
  const { t } = useI18n();
  if (pages <= 1) return null;
  const btn = "grid h-10 min-w-10 place-items-center rounded-full px-3 text-[15px] transition disabled:pointer-events-none disabled:opacity-30";
  return (
    <nav aria-label={t("page.nav")} className="flex flex-wrap items-center justify-center gap-1.5 pt-6">
      <button className={cn(btn, "bg-surface-2 text-fg hover:bg-surface-3")} disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label={t("page.prev")}><ChevronLeft className="size-4" /></button>
      {pageItems(page, pages).map((it, i) => it === "gap"
        ? <span key={`g${i}`} aria-hidden className="px-1 text-fg-3">…</span>
        : <button key={it} onClick={() => onPage(it)} aria-label={t("page.n", { n: it })} aria-current={it === page ? "page" : undefined}
            className={cn(btn, it === page ? "bg-accent text-white" : "text-fg-2 hover:bg-surface-2 hover:text-fg")}>{it}</button>)}
      <button className={cn(btn, "bg-surface-2 text-fg hover:bg-surface-3")} disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label={t("page.next")}><ChevronRight className="size-4" /></button>
    </nav>
  );
}
