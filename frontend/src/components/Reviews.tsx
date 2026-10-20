import { useQuery } from "@tanstack/react-query";
import { Star } from "lucide-react";
import { api } from "@/lib/api";

interface ReviewsData { average: number | null; count: number; reviews: { score: number; text: string; date: string }[] }

/** Community scores and reviews. Authors are anonymous; text is rendered as plain text (React escapes it). */
export function Reviews({ slug }: { slug: string }) {
  const { data } = useQuery({ queryKey: ["reviews", slug], queryFn: () => api<ReviewsData>(`/games/${slug}/reviews`) });
  if (!data) return null;
  return (
    <section className="space-y-5" aria-labelledby="reviews">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h2 id="reviews" className="text-2xl">Player reviews</h2>
        {data.average !== null && <span className="inline-flex items-center gap-1.5 text-fg-2"><Star className="size-4 fill-warning text-warning" />{data.average}/10 · {data.count} {data.count === 1 ? "rating" : "ratings"}</span>}
      </div>
      {data.reviews.length === 0 ? (
        <p className="text-fg-2">No written reviews yet.</p>
      ) : (
        <ul className="grid gap-4 md:grid-cols-2">
          {data.reviews.map((r, i) => (
            <li key={i} className="rounded-lg bg-surface p-5 shadow-card">
              <div className="mb-2 flex items-center justify-between text-sm text-fg-3"><span className="font-medium text-fg">{r.score}/10</span><time dateTime={r.date}>{r.date}</time></div>
              <p className="whitespace-pre-line break-words text-[15px] text-fg-2">{r.text}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
