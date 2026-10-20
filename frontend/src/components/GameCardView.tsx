import { Star } from "lucide-react";
import { Link } from "react-router-dom";
import type { GameCard } from "@/lib/types";
import { formatPrice, hoursLabel, label } from "@/lib/utils";
import { Badge } from "./ui/badge";
import { Cover } from "./Cover";
import { WishlistButton } from "./WishlistButton";

export function GameCardView({ game, reasons, compat }: { game: GameCard; reasons?: string[]; compat?: string | null }) {
  const hours = hoursLabel(game.avg_duration_hours);
  return (
    <Link to={`/games/${game.slug}`} className="lift group block overflow-hidden rounded-lg bg-surface shadow-card fade-in">
      <div className="relative">
        <Cover slug={game.slug} title={game.title} url={game.cover_url} className="aspect-[16/10]" />
        <div className="absolute right-3 top-3"><WishlistButton slug={game.slug} /></div>
        {compat === "below_minimum" && <Badge tone="negative" className="material absolute left-3 top-3">Won’t run on your PC</Badge>}
        {compat === "recommended" && <Badge tone="positive" className="material absolute left-3 top-3">Runs great on your PC</Badge>}
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
          <p className="flex gap-1.5 text-[13px] leading-snug text-fg-2"><span className="spark shrink-0">✦</span><span className="line-clamp-2">{reasons[0]}</span></p>
        )}
      </div>
    </Link>
  );
}

export const CardSkeletons = ({ n = 8 }: { n?: number }) => (
  <>{Array.from({ length: n }, (_, i) => <div key={i} className="h-[300px] animate-pulse rounded-lg bg-surface" />)}</>
);
