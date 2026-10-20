import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useInvalidateUserData } from "@/lib/queries";
import { cn } from "@/lib/utils";
import { Button } from "./ui/button";

interface Mine { score: number | null; review: string | null }

/** Your score (1–10) and optional written review. Review text is plain text everywhere it is shown. */
export function RatingBox({ slug }: { slug: string }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const invalidate = useInvalidateUserData();
  const mine = useQuery({ queryKey: ["my-rating", slug], queryFn: () => api<Mine>(`/me/ratings/${slug}`) });
  const [score, setScore] = useState<number | null>(null);
  const [review, setReview] = useState("");
  useEffect(() => { if (mine.data) { setScore(mine.data.score); setReview(mine.data.review ?? ""); } }, [mine.data]);

  const refresh = () => Promise.all([qc.invalidateQueries({ queryKey: ["my-rating", slug] }), qc.invalidateQueries({ queryKey: ["reviews", slug] }), invalidate()]);
  const save = useMutation({ mutationFn: () => api(`/me/ratings/${slug}`, { method: "PUT", body: { score, review: review.trim() || null } }), onSuccess: refresh });
  const remove = useMutation({ mutationFn: () => api(`/me/ratings/${slug}`, { method: "DELETE" }), onSuccess: async () => { setScore(null); setReview(""); await refresh(); } });
  const dirty = score !== (mine.data?.score ?? null) || review.trim() !== (mine.data?.review ?? "");

  return (
    <section className="space-y-4 rounded-lg bg-surface p-5 shadow-card" aria-labelledby="your-rating">
      <h3 id="your-rating" className="text-lg">{t("rating.title")}</h3>
      <div className="flex flex-wrap items-center gap-1" role="group" aria-label={t("rating.group")}>
        {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
          <button key={n} aria-label={t("rating.out_of", { n })} aria-pressed={score === n} onClick={() => setScore(n)}
            className={cn("size-8 rounded-full text-sm font-medium transition hover:scale-105", score !== null && n <= score ? "bg-warning text-black" : "bg-surface-2 text-fg-3")}>{n}</button>
        ))}
      </div>
      <div>
        <label htmlFor="review" className="sr-only">{t("rating.review")}</label>
        <textarea id="review" value={review} onChange={(e) => setReview(e.target.value)} maxLength={2000} rows={3}
          placeholder={t("rating.placeholder")}
          className="w-full resize-y rounded-md bg-surface-2 px-4 py-3 text-[15px] text-fg outline-none ring-1 ring-transparent placeholder:text-fg-3 focus:ring-accent" />
        <div className="mt-1 text-right text-xs text-fg-3">{review.length}/2000</div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button size="sm" disabled={score === null || !dirty || save.isPending} onClick={() => save.mutate()}>{save.isPending ? t("saving") : t("save")}</Button>
        {mine.data?.score != null && <Button size="sm" variant="ghost" onClick={() => remove.mutate()}>{t("rating.remove")}</Button>}
        {score === null && <span className="text-sm text-fg-3">{t("rating.pick")}</span>}
        {save.isSuccess && !dirty && <span className="text-sm text-positive">{t("saved")}</span>}
        {save.isError && <span role="alert" className="text-sm text-negative">{errorMessage(save.error)}</span>}
      </div>
    </section>
  );
}
