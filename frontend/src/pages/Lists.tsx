import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import type { LibraryEntry } from "@/lib/types";
import { CardSkeletons, GameCardView } from "@/components/GameCardView";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useInvalidateUserData, useLibrary, useWishlist } from "@/lib/queries";
import { RequireAuth } from "./Auth";

const Empty = ({ text }: { text: string }) => {
  const { t } = useI18n();
  return <div className="py-24 text-center"><p className="text-xl text-fg-2">{text}</p><Button asChild className="mt-6"><Link to="/games">{t("lists.browse")}</Link></Button></div>;
};

export function Wishlist() {
  const { t } = useI18n();
  const { data, isLoading } = useWishlist();
  return (
    <RequireAuth>
      <h1 className="mb-8 text-4xl">{t("wishlist.title")}</h1>
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{isLoading ? <CardSkeletons n={4} /> : data?.map((g) => <GameCardView key={g.slug} game={g} />)}</div>
      {data?.length === 0 && <Empty text={t("wishlist.empty")} />}
    </RequireAuth>
  );
}

const STATUSES = ["owned", "playing", "completed", "dropped"] as const;

function LibraryItem({ entry }: { entry: LibraryEntry }) {
  const { t } = useI18n();
  const invalidate = useInvalidateUserData();
  // Local state is the source of truth while editing: both fields are always sent together, so a quick
  // status change followed by an hours edit can never overwrite one with a stale value from props.
  const [status, setStatus] = useState(entry.status);
  const [hours, setHours] = useState(String(Math.round(entry.playtime_minutes / 60)));
  const slug = entry.game.slug;
  const put = useMutation({
    mutationFn: (v: { status: string; playtime_minutes: number }) => api(`/me/library/${slug}`, { method: "PUT", body: v }),
    onSuccess: invalidate,
  });
  const remove = useMutation({ mutationFn: () => api(`/me/library/${slug}`, { method: "DELETE" }), onSuccess: invalidate });
  const minutes = () => Math.min(10000, Math.max(0, Math.round(Number(hours) || 0))) * 60;
  return (
    <div className="space-y-3">
      <GameCardView game={entry.game} />
      <div className="flex flex-wrap items-center gap-2 px-1 text-sm">
        <label className="sr-only" htmlFor={`st-${slug}`}>{t("library.status")}</label>
        <select id={`st-${slug}`} value={status} onChange={(e) => { setStatus(e.target.value); put.mutate({ status: e.target.value, playtime_minutes: minutes() }); }}
          className="h-8 rounded-full bg-surface-2 px-3 text-fg outline-none">
          {STATUSES.map((v) => <option key={v} value={v}>{t(`status.${v}`)}</option>)}
        </select>
        <label className="sr-only" htmlFor={`h-${slug}`}>{t("library.hours")}</label>
        <input id={`h-${slug}`} type="number" min={0} max={10000} value={hours} onChange={(e) => setHours(e.target.value)}
          onBlur={() => { if (minutes() !== entry.playtime_minutes) put.mutate({ status, playtime_minutes: minutes() }); }}
          className="h-8 w-16 rounded-full bg-surface-2 px-3 text-center text-fg outline-none" />
        <span className="text-fg-3">{t("library.h_played")}</span>
        <button onClick={() => remove.mutate()} className="ml-auto text-fg-3 hover:text-negative">{t("remove")}</button>
      </div>
    </div>
  );
}

export function LibraryPage() {
  const { t } = useI18n();
  const { data, isLoading } = useLibrary();
  const { me } = useAuth();
  return (
    <RequireAuth>
      <h1 className="mb-2 text-4xl">{t("library.title")}</h1>
      <p className="mb-8 text-fg-2">{t("library.sub")}</p>
      <div className="grid gap-x-5 gap-y-8 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {isLoading ? <CardSkeletons n={4} /> : data?.map((e) => <LibraryItem key={e.game.slug} entry={e} />)}
      </div>
      {me && data?.length === 0 && <Empty text={t("library.empty")} />}
    </RequireAuth>
  );
}
