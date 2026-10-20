import { ArrowUp } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const EXAMPLES = ["search.ex1", "search.ex2", "search.ex3"] as const;

/** The hero of the product: say what you want to play. Navigates to /discover?q=… */
export function SmartSearch({ size = "lg", initial = "", autoFocus = false }: { size?: "lg" | "sm"; initial?: string; autoFocus?: boolean }) {
  const { t } = useI18n();
  const [q, setQ] = useState(initial);
  const nav = useNavigate();
  const go = (text: string) => text.trim().length >= 2 && nav(`/discover?q=${encodeURIComponent(text.trim().slice(0, 300))}`);
  return (
    <div className="w-full">
      <form onSubmit={(e) => { e.preventDefault(); go(q); }} role="search"
        className={cn("flex items-center gap-3 rounded-full bg-surface pl-5 pr-2 shadow-card ring-1 ring-separator transition focus-within:ring-2 focus-within:ring-accent", size === "lg" ? "h-16" : "h-11")}>
        <span aria-hidden className="spark text-xl">✦</span>
        <input value={q} onChange={(e) => setQ(e.target.value)} maxLength={300} autoFocus={autoFocus} aria-label={t("search.aria")}
          placeholder={t("search.placeholder")}
          className={cn("min-w-0 flex-1 bg-transparent text-fg outline-none placeholder:text-fg-3", size === "lg" ? "text-lg" : "text-[15px]")} />
        <button type="submit" aria-label={t("search.button")} disabled={q.trim().length < 2}
          className={cn("grid place-items-center rounded-full bg-accent text-white transition enabled:hover:bg-accent-hover enabled:active:scale-90 disabled:opacity-30", size === "lg" ? "size-12" : "size-8")}>
          <ArrowUp className={size === "lg" ? "size-5" : "size-4"} />
        </button>
      </form>
      {size === "lg" && (
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          {EXAMPLES.map((k) => t(k)).map((ex) => (
            <button key={ex} onClick={() => { setQ(ex); go(ex); }} className="rounded-full bg-surface-2/70 px-3.5 py-1.5 text-sm text-fg-2 transition hover:bg-surface-3 hover:text-fg">{ex}</button>
          ))}
        </div>
      )}
    </div>
  );
}
