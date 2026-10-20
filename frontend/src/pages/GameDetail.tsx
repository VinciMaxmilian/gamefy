import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, ExternalLink, Star } from "lucide-react";
import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Cover } from "@/components/Cover";
import { GameCardView } from "@/components/GameCardView";
import { Rail } from "@/components/Rail";
import { RatingBox } from "@/components/RatingBox";
import { Reviews } from "@/components/Reviews";
import { WishlistButton } from "@/components/WishlistButton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { reasonText, useI18n } from "@/lib/i18n";
import { useInvalidateUserData, useLibrary } from "@/lib/queries";
import type { GameCard, GameDetail as Detail } from "@/lib/types";
import { cn, formatPrice, hoursLabel, label } from "@/lib/utils";

const VERDICT = {
  recommended: { tone: "positive", key: "verdict.recommended" },
  partial: { tone: "warning", key: "verdict.partial" },
  minimum: { tone: "warning", key: "verdict.minimum" },
  below_minimum: { tone: "negative", key: "verdict.below_minimum" },
  unknown: { tone: "neutral", key: "verdict.unknown" },
} as const;
const REQ_KEYS = ["gpu_tier", "cpu_tier", "ram_gb", "vram_gb", "storage_gb"] as const;

export default function GameDetail() {
  const { t } = useI18n();
  const { slug = "" } = useParams();
  const nav = useNavigate();
  const { me } = useAuth();
  const invalidate = useInvalidateUserData();
  const game = useQuery({ queryKey: ["game", slug, me?.email], queryFn: () => api<Detail>(`/games/${slug}`), retry: false });
  const similar = useQuery({ queryKey: ["similar", slug], queryFn: () => api<GameCard[]>(`/games/${slug}/similar`), enabled: game.isSuccess });
  const library = useLibrary();
  const owned = library.data?.find((e) => e.game.slug === slug);

  useEffect(() => { if (me && game.isSuccess) api("/me/events", { method: "POST", body: { type: "view", slug } }).catch(() => {}); }, [me, game.isSuccess, slug]);

  const addLibrary = useMutation({
    mutationFn: (on: boolean) => on ? api(`/me/library/${slug}`, { method: "PUT", body: { status: "owned", playtime_minutes: 0 } }) : api(`/me/library/${slug}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });

  if (game.isError) return <div className="py-24 text-center"><h1 className="text-3xl">{t("game.not_found")}</h1><Button asChild className="mt-6"><Link to="/games">{t("game.back")}</Link></Button></div>;
  const g = game.data;
  if (!g) return <div className="h-[420px] animate-pulse rounded-xl bg-surface" />;
  const v = g.compatibility ? VERDICT[g.compatibility.verdict] : null;

  return (
    <article className="space-y-14">
      <div className="grid gap-8 lg:grid-cols-[1.4fr_1fr]">
        <Cover slug={g.slug} title={g.title} url={g.cover_url} className="aspect-[16/10] rounded-xl shadow-pop" />
        <div className="space-y-6">
          <div>
            <div className="mb-3 flex flex-wrap gap-2">{g.genres.map((x) => <Badge key={x} tone="accent">{label(x)}</Badge>)}</div>
            <h1 className="text-4xl md:text-5xl">{g.title}</h1>
            {g.developer && <p className="mt-2 text-fg-2">{g.developer}{g.release_date ? ` · ${g.release_date.slice(0, 4)}` : ""}</p>}
          </div>
          <p className="text-lg text-fg-2">{g.summary}</p>
          <div className="flex flex-wrap items-center gap-5 text-fg-2">
            {g.rating !== null && <span className="inline-flex items-center gap-1.5 text-lg text-fg"><Star className="size-5 fill-warning text-warning" />{g.rating}<span className="text-sm text-fg-3">/100</span></span>}
            {hoursLabel(g.avg_duration_hours) && <span>{t("game.to_play", { hours: hoursLabel(g.avg_duration_hours) ?? "" })}</span>}
            {g.difficulty && <span>{t("game.difficulty", { n: g.difficulty })}</span>}
          </div>
          {v && g.compatibility && <div className={cn("rounded-lg p-4", `bg-${v.tone === "neutral" ? "surface-2" : v.tone}/10`)}><p className="font-medium">{t(v.key)}</p><p className="mt-1 text-sm text-fg-2">{g.compatibility.reasons.map(reasonText).join(" · ")}</p></div>}
          {me && !g.compatibility && <p className="text-sm text-fg-3"><Link to="/profile" className="text-accent">{t("game.add_pc_link")}</Link>{t("game.add_pc_rest")}</p>}
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <span className="mr-2 text-3xl font-semibold tracking-tight">{g.stores.some((o) => o.price_cents !== null) ? <span className="mr-1.5 text-base font-normal text-fg-3">{t("price.from")}</span> : null}{formatPrice(g.price_cents, g.currency)}</span>
            <Button size="lg" onClick={() => me ? addLibrary.mutate(!owned) : nav("/login")} variant={owned ? "secondary" : "primary"}>{owned ? <><Check className="size-5" />{t("game.in_library")}</> : t("game.add_library")}</Button>
            <WishlistButton slug={g.slug} variant="full" />
          </div>
        </div>
      </div>

      {g.stores.length > 0 && (
        <section className="space-y-4" aria-labelledby="buy">
          <h2 id="buy" className="text-2xl">{t("buy.title")}</h2>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {g.stores.map((o) => (
              <li key={o.store}>
                {/* Outbound link: allow-listed host (validated server-side), no referrer/opener leakage, marked as sponsored. */}
                <a href={o.url} target="_blank" rel="noopener noreferrer nofollow sponsored"
                  className="lift flex items-center justify-between gap-4 rounded-lg bg-surface p-4 shadow-card">
                  <div><div className="font-medium">{o.name}</div>
                    <div className="mt-0.5 flex items-center gap-2 text-sm text-fg-3">
                      {o.discount_percent > 0 && <Badge tone="positive">-{o.discount_percent}%</Badge>}
                      {o.normal_price_cents !== null && o.discount_percent > 0 && <s>{formatPrice(o.normal_price_cents, o.currency)}</s>}
                      {o.price_cents === null && <span>{t("buy.view_price")}</span>}
                    </div></div>
                  <div className="flex items-center gap-2 text-lg font-semibold">{o.price_cents !== null && formatPrice(o.price_cents, o.currency)}<ExternalLink className="size-4 text-fg-3" aria-hidden /></div>
                </a>
              </li>))}
          </ul>
          <p className="text-xs text-fg-3">{t("buy.disclaimer")}</p>
        </section>
      )}

      <div className="grid gap-10 lg:grid-cols-2">
        <section className="space-y-4"><h2 className="text-2xl">{t("game.about")}</h2><p className="whitespace-pre-line text-fg-2">{g.description}</p>
          <div className="flex flex-wrap gap-2">{[...g.features, ...g.tags].map((t) => <Badge key={t}>{label(t)}</Badge>)}</div>
          <div className="flex flex-wrap gap-2 pt-2">{g.platforms.map((p) => <Badge key={p} tone="neutral" className="uppercase">{p}</Badge>)}</div>
        </section>
        <section className="space-y-4"><h2 className="text-2xl">{t("game.reqs")}</h2>
          <div className="overflow-hidden rounded-lg bg-surface">
            <table className="w-full text-left text-[15px]">
              <thead className="text-sm text-fg-3"><tr><th className="p-3 font-medium"></th><th className="p-3 font-medium">{t("req.min")}</th><th className="p-3 font-medium">{t("req.rec")}</th></tr></thead>
              <tbody>{REQ_KEYS.map((k) => (
                <tr key={k} className="border-t border-separator"><td className="p-3 text-fg-2">{t(`req.${k}`)}</td><td className="p-3">{g.req.min?.[k] ?? "—"}</td><td className="p-3">{g.req.rec?.[k] ?? "—"}</td></tr>))}</tbody>
            </table>
          </div>
          <p className="text-xs text-fg-3">{t("game.tiers_note")}</p>
        </section>
      </div>

      <Reviews slug={g.slug} />
      {me && <div className="max-w-2xl"><RatingBox slug={g.slug} /></div>}

      {similar.data && similar.data.length > 0 && (
        <Rail title={<><span className="spark">✦</span> {t("game.similar")}</>} subtitle={t("game.similar_sub")}>
          {similar.data.slice(0, 4).map((s) => <GameCardView key={s.slug} game={s} />)}
        </Rail>
      )}
    </article>
  );
}
