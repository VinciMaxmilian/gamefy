import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { CardSkeletons, GameCardView } from "@/components/GameCardView";
import { SmartSearch } from "@/components/SmartSearch";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, ApiError, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useInvalidateUserData } from "@/lib/queries";
import type { SmartResult } from "@/lib/types";
import { formatPrice, label } from "@/lib/utils";

export default function Discover() {
  const { t } = useI18n();
  const [sp] = useSearchParams();
  const q = (sp.get("q") ?? "").slice(0, 300);
  const { me, refresh } = useAuth();
  const invalidate = useInvalidateUserData();
  const res = useQuery({
    queryKey: ["smart", q, me?.email], enabled: !!me && q.length >= 2, retry: false, staleTime: 5 * 60_000,
    queryFn: async () => { const r = await api<SmartResult>("/search/smart", { query: { q, fits_my_pc: true } }); refresh(); invalidate(); return r; },
  });
  const u = res.data?.understood;
  const chips = u ? [...u.similar_to.map((s) => t("discover.like", { title: s })), ...[...u.genres, ...u.tags, ...u.features, ...u.platforms].map(label), ...(u.max_price_cents !== null ? [t("discover.under", { price: formatPrice(u.max_price_cents) })] : []), ...(u.max_duration_hours ? [`≤ ${u.max_duration_hours}h`] : [])] : [];
  const err = res.error instanceof ApiError ? res.error : null;

  return (
    <div className="space-y-8">
      <div className="mx-auto max-w-3xl"><SmartSearch size="sm" initial={q} /></div>
      {!me && (
        <Gate title={t("discover.gate_title")} body={t("discover.gate_body")}>
          <Button asChild><Link to="/signup">{t("discover.create_free")}</Link></Button>
          <Button asChild variant="secondary"><Link to={`/games?q=${encodeURIComponent(q)}`}>{t("discover.classic")}</Link></Button>
        </Gate>
      )}
      {err?.status === 429 && <Gate title={t("discover.quota_title")} body={t("discover.quota_body")}>
        <Button asChild><Link to="/premium">{t("discover.see_premium")}</Link></Button><Button asChild variant="secondary"><Link to={`/games?q=${encodeURIComponent(q)}`}>{t("discover.classic_short")}</Link></Button></Gate>}
      {err && err.status !== 429 && <Gate title={t("discover.unavailable")} body={errorMessage(err)}>
        <Button asChild variant="secondary"><Link to={`/games?q=${encodeURIComponent(q)}`}>{t("discover.classic")}</Link></Button></Gate>}

      {res.isLoading && me && <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4"><CardSkeletons n={8} /></div>}
      {res.data && (
        <>
          <div className="space-y-3">
            <p className="text-fg-2"><span className="spark">✦</span> {t("discover.understood")}</p>
            <div className="flex flex-wrap gap-2">{chips.length ? chips.map((c) => <Badge key={c} tone="accent" className="px-3 py-1 text-sm">{c}</Badge>) : <span className="text-sm text-fg-3">{t("discover.by_meaning")}</span>}</div>
            <p className="text-sm text-fg-3">{t("discover.left", { n: res.data.remaining_today })}</p>
            {res.data.mode === "keyword" && <p className="text-sm text-fg-3">{t("discover.keyword_note")}</p>}
          </div>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
            {res.data.items.map((r) => <GameCardView key={r.game.slug} game={r.game} reasons={r.reasons} compat={r.compatibility?.verdict} dismissible />)}
          </div>
        </>
      )}
    </div>
  );
}

const Gate = ({ title, body, children }: { title: string; body: string; children: React.ReactNode }) => (
  <div className="mx-auto max-w-xl rounded-xl bg-surface p-8 text-center shadow-card">
    <h2 className="text-2xl">{title}</h2><p className="mt-2 text-fg-2">{body}</p><div className="mt-6 flex flex-wrap justify-center gap-3">{children}</div>
  </div>
);
