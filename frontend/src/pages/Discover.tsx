import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { CardSkeletons, GameCardView } from "@/components/GameCardView";
import { SmartSearch } from "@/components/SmartSearch";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, ApiError, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useInvalidateUserData } from "@/lib/queries";
import type { SmartResult } from "@/lib/types";
import { formatPrice, label } from "@/lib/utils";

export default function Discover() {
  const [sp] = useSearchParams();
  const q = (sp.get("q") ?? "").slice(0, 300);
  const { me, refresh } = useAuth();
  const invalidate = useInvalidateUserData();
  const res = useQuery({
    queryKey: ["smart", q, me?.email], enabled: !!me && q.length >= 2, retry: false, staleTime: 5 * 60_000,
    queryFn: async () => { const r = await api<SmartResult>("/search/smart", { query: { q, fits_my_pc: true } }); refresh(); invalidate(); return r; },
  });
  const u = res.data?.understood;
  const chips = u ? [...u.similar_to.map((s) => `like ${s}`), ...u.genres, ...u.tags, ...u.features, ...u.platforms, ...(u.max_price_cents !== null ? [`under ${formatPrice(u.max_price_cents)}`] : []), ...(u.max_duration_hours ? [`≤ ${u.max_duration_hours}h`] : [])] : [];
  const err = res.error instanceof ApiError ? res.error : null;

  return (
    <div className="space-y-8">
      <div className="mx-auto max-w-3xl"><SmartSearch size="sm" initial={q} /></div>
      {!me && (
        <Gate title="Smart search is free with an account" body="Sign up to describe what you want to play and get matches ranked for your taste.">
          <Button asChild><Link to="/signup">Create free account</Link></Button>
          <Button asChild variant="secondary"><Link to={`/games?q=${encodeURIComponent(q)}`}>Use classic search</Link></Button>
        </Gate>
      )}
      {err?.status === 429 && <Gate title="You’ve used today’s smart searches" body="Free accounts get a few each day. Classic search and your recommendations are always available.">
        <Button asChild><Link to="/premium">See Premium</Link></Button><Button asChild variant="secondary"><Link to={`/games?q=${encodeURIComponent(q)}`}>Classic search</Link></Button></Gate>}
      {err && err.status !== 429 && <Gate title="Smart search is unavailable right now" body={errorMessage(err)}>
        <Button asChild variant="secondary"><Link to={`/games?q=${encodeURIComponent(q)}`}>Use classic search</Link></Button></Gate>}

      {res.isLoading && me && <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4"><CardSkeletons n={8} /></div>}
      {res.data && (
        <>
          <div className="space-y-3">
            <p className="text-fg-2"><span className="spark">✦</span> Here’s what we understood</p>
            <div className="flex flex-wrap gap-2">{chips.length ? chips.map((c) => <Badge key={c} tone="accent" className="px-3 py-1 text-sm">{label(c)}</Badge>) : <span className="text-sm text-fg-3">Matching by overall meaning.</span>}</div>
            <p className="text-sm text-fg-3">{res.data.remaining_today} smart searches left today</p>
          </div>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
            {res.data.items.map((r) => <GameCardView key={r.game.slug} game={r.game} reasons={r.reasons} compat={r.compatibility?.verdict} />)}
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
