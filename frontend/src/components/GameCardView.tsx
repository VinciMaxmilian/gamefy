import { EyeOff, Star } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { reasonText, useI18n } from "@/lib/i18n";
import { useInvalidateUserData } from "@/lib/queries";
import type { GameCard, Reason } from "@/lib/types";
import { formatPrice, hoursLabel, label } from "@/lib/utils";
import { Badge } from "./ui/badge";
import { Cover } from "./Cover";
import { WishlistButton } from "./WishlistButton";

export function GameCardView({ game, reasons, compat, dismissible }: { game: GameCard; reasons?: Reason[]; compat?: string | null; dismissible?: boolean }) {
  const hours = hoursLabel(game.avg_duration_hours);
  const { me } = useAuth();
  const { t } = useI18n();
  const invalidate = useInvalidateUserData();
  const [gone, setGone] = useState(false);
  if (gone) return null;
  const dismiss = (e: React.MouseEvent) => {
    e.preventDefault(); e.stopPropagation();
    setGone(true);
    api("/me/events", { method: "POST", body: { type: "ignore", slug: game.slug } }).then(invalidate).catch(() => setGone(false));
  };
  return (
    <Link to={`/games/${game.slug}`} className="lift group block overflow-hidden rounded-lg bg-surface shadow-card fade-in">
      <div className="relative">
        <Cover slug={game.slug} title={game.title} url={game.cover_url} className="aspect-[16/10]" />
        <div className="absolute right-3 top-3 flex flex-col gap-2">
          <WishlistButton slug={game.slug} />
          {dismissible && me && (
            <button onClick={dismiss} aria-label={t("card.not_interested_in", { title: game.title })} title={t("card.not_interested")}
              className="material grid size-9 place-items-center rounded-full text-fg transition hover:scale-105 active:scale-95 md:opacity-0 md:group-hover:opacity-100 md:focus-visible:opacity-100">
              <EyeOff className="size-[18px]" />
            </button>
          )}
        </div>
        {compat === "below_minimum" && <Badge tone="negative" className="material absolute left-3 top-3">{t("card.wont_run")}</Badge>}
        {compat === "recommended" && <Badge tone="positive" className="material absolute left-3 top-3">{t("card.runs_great")}</Badge>}
      </div>
      <div className="space-y-2 p-4">
        <div className="flex items-start justify-between gap-3">
          <h3 className="line-clamp-1 text-[17px] font-semibold tracking-tight">{game.title}</h3>
          <span className="shrink-0 text-[15px] font-medium text-fg-2">{formatPrice(game.price_cents, game.currency)}</span>
        </div>
        <div className="flex items-center gap-3 text-sm text-fg-3">
          {game.rating !== null && <span className="inline-flex items-center gap-1"><Star className="size-3.5 fill-warning text-warning" />{game.rating}</span>}
          {hours && <span>{hours}</span>}
          <span className="line-clamp-1 capitalize">{game.genres.slice(0, 2).map(label).join(" · ")}</span>
        </div>
        {reasons && reasons.length > 0 && (
          <p className="flex gap-1.5 text-[13px] leading-snug text-fg-2"><span className="spark shrink-0">✦</span><span className="line-clamp-2">{reasonText(reasons[0])}</span></p>
        )}
      </div>
    </Link>
  );
}

export const CardSkeletons = ({ n = 8 }: { n?: number }) => (
  <>{Array.from({ length: n }, (_, i) => <div key={i} className="h-[300px] animate-pulse rounded-lg bg-surface" />)}</>
);
