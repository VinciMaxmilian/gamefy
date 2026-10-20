import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { CardSkeletons, GameCardView } from "@/components/GameCardView";
import { Rail } from "@/components/Rail";
import { Spark } from "@/components/Spark";
import { SmartSearch } from "@/components/SmartSearch";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { Page, Recommendation } from "@/lib/types";
import { label } from "@/lib/utils";

const GENRES = ["rpg", "action", "adventure", "strategy", "indie", "puzzle", "horror", "simulation"];

export default function Home() {
  const { me } = useAuth();
  const { t } = useI18n();
  const { hash } = useLocation();
  const forYou = useQuery({
    queryKey: ["for-you"], enabled: !!me,
    queryFn: () => api<{ personalized: boolean; items: Recommendation[] }>("/reco/for-you", { query: { limit: 8 } }),
  });
  const top = useQuery({ queryKey: ["top"], queryFn: () => api<Page>("/games", { query: { sort: "rating", limit: 8 } }) });

  return (
    <div className="space-y-20">
      <section className="relative mx-auto max-w-4xl pt-8 text-center md:pt-16">
        <h1 className="text-balance text-[2.6rem] leading-[1.05] md:text-[3.75rem]">
          {t("home.title1")}<br /><span className="text-fg-2">{t("home.title2")}</span>
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-lg text-fg-2 md:text-xl">{t("home.sub")}</p>
        <div className="mt-9"><SmartSearch autoFocus={hash === "#search"} /></div>
        {!me && <p className="mt-5 text-sm text-fg-3"><Link to="/signup" className="text-accent hover:underline">{t("home.guest_link")}</Link>{t("home.guest_rest")}</p>}
      </section>

      {me && (
        <Rail
          title={<><Spark /> {t("home.picked")}</>}
          subtitle={forYou.data && !forYou.data.personalized ? t("home.picked_empty") : t("home.picked_sub")}
          action={<Button asChild variant="ghost" size="sm"><Link to="/profile">{t("home.your_taste")}</Link></Button>}>
          {forYou.isLoading ? <CardSkeletons n={4} /> : forYou.data?.items.slice(0, 8).map((r) => <GameCardView key={r.game.slug} game={r.game} reasons={r.reasons} compat={r.compatibility?.verdict} dismissible />)}
        </Rail>
      )}

      {top.data && top.data.items.length === 0 && (
        <p className="rounded-lg bg-surface p-8 text-center text-fg-2">{t("home.setup")}</p>
      )}

      <Rail title={t("home.top")} subtitle={t("home.top_sub")} action={<Button asChild variant="ghost" size="sm"><Link to="/games?sort=rating">{t("home.see_all")}</Link></Button>}>
        {top.isLoading ? <CardSkeletons n={4} /> : top.data?.items.map((g) => <GameCardView key={g.slug} game={g} />)}
      </Rail>

      <section className="space-y-5">
        <h2 className="text-2xl md:text-[1.75rem]">{t("home.browse_genre")}</h2>
        <div className="flex flex-wrap gap-3">
          {GENRES.map((g) => <Link key={g} to={`/games?genres=${g}`} className="rounded-full bg-surface px-5 py-2.5 text-[15px] font-medium text-fg-2 shadow-card transition hover:bg-surface-2 hover:text-fg">{label(g)}</Link>)}
        </div>
      </section>
    </div>
  );
}
